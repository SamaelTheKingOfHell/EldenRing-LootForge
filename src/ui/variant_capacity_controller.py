"""Debounced background capacity calculation for the variants control."""

try:
    from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
    from PySide6.QtWidgets import QApplication
except ImportError:
    from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal as Signal, pyqtSlot as Slot
    from PyQt6.QtWidgets import QApplication

from src.variant_capacity import calculate_capacity, clamp_variants


class CapacityWorker(QThread):
    """Read regulation metadata and simulate row counts without blocking the Qt event loop."""
    ready = Signal(object)
    failed = Signal(object)

    def __init__(self, revision, manager, source, specs, knowledge, vanilla, parent):
        super().__init__(parent)
        self.inputs = revision, manager, source, specs, knowledge, vanilla

    def run(self):
        """Return an immutable capacity result or a visible diagnostic."""
        revision, manager, source, specs, knowledge, vanilla = self.inputs
        try:
            counts = manager.equipment_row_counts(source)
            capacities = {mode: calculate_capacity(counts, specs, knowledge, mode)
                          for mode in (vanilla, not vanilla)}
            self.ready.emit((revision, capacities))
        except Exception as error:
            self.failed.emit((revision, str(error)))


class VariantCapacityController(QObject):
    """Keep the UI maximum synchronized with source regulation, selection, and vanilla inclusion."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.revision = 0
        self.worker = None
        self.capacities = None
        self.source = None
        self.source_identity = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.refresh)
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def schedule(self, vanilla_only=False):
        """Coalesce rapid settings edits and prevent forging against a stale pending limit."""
        self.revision += 1
        if (vanilla_only and self.capacities is not None and self.source_identity is not None
                and self.source_identity == self.current_source_identity()):
            self.timer.stop()
            self.apply((self.revision, self.capacities))
            return
        self.capacities = None
        self.window.diablo_variants_spin.setEnabled(False)
        self.window.diablo_variants_spin.setToolTip("Calculating the maximum for the current selection…")
        self.window.forge_btn.setEnabled(False)
        self.timer.start(300)

    def current_source_identity(self):
        """Invalidate paired limits when the regulation or deployed native tool changes."""
        try:
            paths = (self.source, self.window.regulation_manager.regtool_dll)
            return tuple((str(path), path.stat().st_size, path.stat().st_mtime_ns)
                         for path in paths if path is not None)
        except OSError:
            return None

    @Slot()
    def refresh(self):
        """Capture current selection on the UI thread, then run the expensive work in a worker."""
        if self.worker and self.worker.isRunning():
            self.timer.start(300)
            return
        window = self.window
        source = window.regulation_manager.resolve_source_regulation(
            window.active_reg_input.text().strip(), window.config.game_directory, window.config.output_directory)
        if source is None or not source.exists():
            self.failed("Select an existing source regulation to calculate the maximum.")
            return
        self.source = source
        self.source_identity = self.current_source_identity()
        specs = [window.param_builder.build_patch_spec(mod, include_custom_art=False)
                 for mod in window.scanned_sets if getattr(mod, "is_enabled", True)]
        self.worker = CapacityWorker(self.revision, window.regulation_manager, source, specs,
                                     window.knowledge_base, window.config.diablo_use_vanilla_base_items, self)
        self.worker.ready.connect(self.apply)
        self.worker.failed.connect(self.worker_failed)
        worker = self.worker
        worker.finished.connect(lambda: self.release_worker(worker))
        self.worker.start()

    def release_worker(self, worker):
        """Release each finished worker and its captured selection."""
        if self.worker is worker:
            self.worker = None
        worker.deleteLater()

    @Slot(object)
    def apply(self, result):
        """Apply only the latest selection's result and persist a clamped value once."""
        revision, capacities = result
        if revision != self.revision:
            self.timer.start(1)
            return
        if self.source_identity != self.current_source_identity():
            self.schedule()
            return
        self.capacities = capacities
        window = self.window
        capacity = capacities[bool(window.config.diablo_use_vanilla_base_items)]
        spin = window.diablo_variants_spin
        spin.blockSignals(True)
        spin.setMaximum(max(1, capacity.maximum))
        spin.setToolTip(f"Maximum for this regulation and selection: {capacity.maximum}. Includes companion talismans and existing rows.")
        if capacity.maximum:
            if clamp_variants(window.config, capacity):
                window.config.save(window.config_path)
            spin.setValue(window.config.diablo_variants_per_item)
        spin.blockSignals(False)
        spin.setEnabled(capacity.maximum > 0)
        window.forge_btn.setEnabled(capacity.maximum > 0)
        self.capacity = capacity

    @Slot(object)
    def worker_failed(self, result):
        """Ignore failures from a source or selection that has already changed."""
        revision, error = result
        if revision != self.revision:
            self.timer.start(1)
            return
        self.failed(error)

    @Slot(str)
    def failed(self, error):
        """Expose unavailable capacity and let forging produce its detailed validation error."""
        self.window.diablo_variants_spin.setToolTip(error)
        self.window.forge_btn.setEnabled(True)

    @Slot()
    def shutdown(self):
        """Let an owned metadata worker finish before Qt destroys its objects."""
        self.timer.stop()
        if self.worker:
            self.worker.wait()
