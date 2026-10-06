"""
Cross-platform HTTP server and API provider for LootForge.

Serves the modern Souls-themed desktop interface and handles REST endpoints for scanning,
asset renumbering, parameter building, backup management, and developer logging.
"""

import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any

from src.config import LootForgeConfig
from src.knowledge_base import VanillaKnowledgeBase
from src.id_allocator import IdAllocator
from src.scanner import ModScanner
from src.asset_renumberer import AssetRenumberer
from src.param_builder import ParamBuilder
from src.backup_manager import BackupManager
from src.manifest_store import ManifestStore
from src.regulation_manager import RegulationManager
from src.logger import system_logger
from src.models import LootDistributionType, LootTarget


class LootForgeRequestHandler(SimpleHTTPRequestHandler):
    """
    HTTP handler processing UI asset requests and API calls.
    """

    # Class-level references set by LootForgeServer
    config: LootForgeConfig
    knowledge_base: VanillaKnowledgeBase
    id_allocator: IdAllocator
    scanner: ModScanner
    asset_renumberer: AssetRenumberer
    param_builder: ParamBuilder
    backup_manager: BackupManager
    manifest_store: ManifestStore
    regulation_manager: RegulationManager
    ui_root: Path
    data_root: Path

    def do_GET(self) -> None:
        """Handles GET requests for static assets and API queries."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api_get(path, urllib.parse.parse_qs(parsed.query))
        else:
            self._serve_static(path)

    def do_POST(self) -> None:
        """Handles POST requests for state-mutating actions."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            body = {}

        if path.startswith("/api/"):
            self._handle_api_post(path, body)
        else:
            self.send_error(404, "Not Found")

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Sends a JSON response with CORS and cache headers."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, path: str) -> None:
        """Serves UI HTML, CSS, and JS files."""
        if path == "/" or path == "":
            file_path = self.ui_root / "index.html"
        else:
            clean_path = path.lstrip("/")
            file_path = self.ui_root / clean_path

        if not file_path.exists() or file_path.is_dir():
            self.send_error(404, "File Not Found")
            return

        # Determine MIME type
        ext = file_path.suffix.lower()
        mime_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml"
        }
        content_type = mime_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def _handle_api_get(self, path: str, query: Dict[str, Any]) -> None:
        """Processes GET API endpoints."""
        if path == "/api/status":
            backups = self.backup_manager.list_backups()
            manifest_records = self.manifest_store.get_all_records()
            self._send_json({
                "config": self.config.to_dict(),
                "backup_count": len(backups),
                "latest_backup": backups[0].backup_file_name if backups else None,
                "injected_count": len(manifest_records),
                "manifest_records": [
                    {
                        "set_id": r.set_id,
                        "name": r.source_mod_name,
                        "target": r.target_vanilla_name,
                        "model_id": r.allocated_model_id,
                        "loot_route": r.loot_route,
                        "loot_target": r.loot_target_name,
                        "timestamp": r.created_timestamp
                    }
                    for r in manifest_records
                ]
            })

        elif path == "/api/localization":
            lang = query.get("lang", [self.config.default_locale])[0]
            loc_path = self.data_root / "localization" / f"{lang}.json"
            if not loc_path.exists():
                loc_path = self.data_root / "localization" / "en.json"

            try:
                with open(loc_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json(data)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/options":
            self._send_json({
                "boss_remembrances": self.knowledge_base.list_boss_remembrances(),
                "elite_enemies": self.knowledge_base.list_elite_enemies(),
                "merchants": self.knowledge_base.list_merchants()
            })

        elif path == "/api/scan":
            try:
                # Scan input mods directory
                detected = self.scanner.scan_directory(self.config.input_directory)
                # Allocate standalone IDs for each set
                self.id_allocator.reset()
                result_sets = []
                for s in detected:
                    alloc = self.id_allocator.allocate(s.set_id)
                    s.allocation = alloc
                    result_sets.append({
                        "set_id": s.set_id,
                        "folder_name": s.folder_or_archive_name,
                        "target_model_id": s.target_model_id,
                        "target_vanilla_name": s.target_vanilla_name,
                        "is_weapon": s.is_weapon,
                        "parts_count": len(s.parts),
                        "allocated_model_id": alloc.new_model_id,
                        "allocated_param_id": alloc.new_equip_param_id,
                        "default_route": s.loot_target.route_type.value if s.loot_target else "enemy_drop",
                        "default_target_id": s.loot_target.target_id if s.loot_target else "",
                        "default_display_name": s.loot_target.display_name if s.loot_target else "",
                        "default_chance_cost": s.loot_target.chance_or_cost if s.loot_target else 20.0
                    })
                self._send_json({"sets": result_sets})
            except Exception as e:
                system_logger.error(f"Scan failed: {e}", source="API")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/logs":
            min_level = query.get("level", [None])[0]
            limit = int(query.get("limit", [100])[0])
            logs = system_logger.get_recent_logs(limit=limit, min_level=min_level)
            self._send_json({"logs": logs, "debug_enabled": system_logger.debug_enabled})

        else:
            self.send_error(404, "Endpoint Not Found")

    def _handle_api_post(self, path: str, body: Dict[str, Any]) -> None:
        """Processes POST API endpoints."""
        if path == "/api/forge":
            try:
                sets_data = body.get("sets", [])
                if not sets_data:
                    self._send_json({"error": "No mod sets provided for forging"}, status=400)
                    return

                system_logger.info(f"Starting forge run for {len(sets_data)} mod set(s)...", source="Forge")
                
                # Rescan to acquire actual file handles
                detected_map = {
                    s.set_id: s for s in self.scanner.scan_directory(self.config.input_directory)
                }

                injected_records = []
                all_specs = []
                for entry in sets_data:
                    set_id = entry.get("set_id")
                    if set_id not in detected_map:
                        continue

                    mod_set = detected_map[set_id]
                    # Assign allocation
                    alloc = self.id_allocator.allocate(mod_set.set_id)
                    mod_set.allocation = alloc

                    # Apply customized loot target if selected in UI
                    custom_route = entry.get("route_type", "enemy_drop")
                    custom_target_id = entry.get("target_id", "")
                    custom_target_name = entry.get("target_name", "Custom Target")
                    custom_cost = float(entry.get("chance_or_cost", 20.0))

                    mod_set.loot_target = LootTarget(
                        route_type=LootDistributionType(custom_route),
                        target_id=custom_target_id,
                        display_name=custom_target_name,
                        chance_or_cost=custom_cost
                    )

                    # 1. Renumber & stage assets
                    staged_files = self.asset_renumberer.stage_mod_set(
                        self.config.input_directory, mod_set
                    )

                    # 2. Build parameter patch spec
                    patch_spec = self.param_builder.build_patch_spec(mod_set)
                    all_specs.append(patch_spec)

                    # 3. Record into manifest
                    record = self.manifest_store.record_set(mod_set, staged_files)
                    injected_records.append(record)

                # Execute regulation creation & injection
                active_reg = body.get("path") or self.config.active_regulation_path or ""
                source_reg = self.regulation_manager.resolve_source_regulation(
                    active_path=active_reg,
                    game_dir=self.config.game_directory,
                    output_dir=self.config.output_directory
                )

                reg_result = None
                if source_reg and source_reg.exists():
                    target_reg = self.regulation_manager.resolve_target_regulation(
                        active_path=active_reg,
                        output_dir=self.config.output_directory,
                        game_dir=self.config.game_directory
                    )

                    if target_reg.exists():
                        try:
                            self.backup_manager.create_backup(str(target_reg))
                        except Exception as be:
                            system_logger.warning(f"Auto-backup notice: {be}", source="Forge")

                    reg_result = self.regulation_manager.execute_patch(all_specs, source_reg, target_reg)
                    self.config.active_regulation_path = str(target_reg)
                    self.config.save()

                system_logger.info(
                    f"Forge successfully completed! {len(injected_records)} set(s) injected.",
                    source="Forge"
                )
                self._send_json({
                    "success": True,
                    "injected_count": len(injected_records),
                    "sets": [r.set_id for r in injected_records],
                    "regulation": reg_result
                })
            except Exception as e:
                system_logger.error(f"Forge execution error: {e}", source="Forge")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/backup":
            try:
                reg_path = body.get("path") or self.config.active_regulation_path or os.path.join(self.config.game_directory, "regulation.bin")
                if not Path(reg_path).exists():
                    Path(reg_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(reg_path, "wb") as f:
                        f.write(b"ELDEN_RING_REGULATION_BIN_HEADER_SNAPSHOT")

                rec = self.backup_manager.create_backup(reg_path)
                self._send_json({"success": True, "backup": rec.backup_file_name})
            except Exception as e:
                system_logger.error(f"Backup creation error: {e}", source="BackupManager")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/restore":
            try:
                reg_path = body.get("path") or self.config.active_regulation_path or os.path.join(self.config.game_directory, "regulation.bin")
                self.backup_manager.restore_latest_backup(reg_path)
                self._send_json({"success": True, "message": "Restored latest regulation backup."})
            except Exception as e:
                system_logger.error(f"Restore error: {e}", source="BackupManager")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/uninstall":
            try:
                # Remove staged files recorded in manifest
                all_records = self.manifest_store.get_all_records()
                for rec in all_records:
                    self.asset_renumberer.cleanup_files(rec.staged_files)

                self.manifest_store.clear()
                system_logger.info("Clean uninstall completed. All staged assets purged.", source="Uninstall")
                self._send_json({"success": True, "message": "Uninstalled all injected mods cleanly."})
            except Exception as e:
                system_logger.error(f"Uninstall error: {e}", source="Uninstall")
                self._send_json({"error": str(e)}, status=500)

        elif path == "/api/config":
            try:
                for k, v in body.items():
                    if hasattr(self.config, k):
                        setattr(self.config, k, v)
                self.config.save()
                system_logger.debug_enabled = self.config.debug_mode
                self._send_json({"success": True, "config": self.config.to_dict()})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)

        else:
            self.send_error(404, "Endpoint Not Found")


class LootForgeServer:
    """
    HTTP Server managing UI and API lifecycle.
    
    Why:
        Provides a zero-install, lightweight runtime accessible via any modern browser
        on Windows or Steam Deck.
    """

    def __init__(self, base_dir: Path, config: LootForgeConfig):
        self.base_dir = base_dir
        self.config = config
        self.knowledge_base = VanillaKnowledgeBase.from_data_dir(str(base_dir / "data"))
        self.id_allocator = IdAllocator(
            min_model_id=config.min_model_id,
            max_model_id=config.max_model_id,
            base_param_id=config.base_param_id,
            base_item_lot_id=config.base_item_lot_id
        )
        self.scanner = ModScanner(self.knowledge_base)
        self.asset_renumberer = AssetRenumberer(str(base_dir / config.output_directory))
        self.param_builder = ParamBuilder()
        self.backup_manager = BackupManager(str(base_dir / config.backup_directory))
        self.manifest_store = ManifestStore(str(base_dir / config.manifest_file))
        self.regulation_manager = RegulationManager(base_dir)
        self.server: Optional[HTTPServer] = None

    def start(self) -> None:
        """Launches the HTTP daemon."""
        handler_cls = LootForgeRequestHandler
        handler_cls.config = self.config
        handler_cls.knowledge_base = self.knowledge_base
        handler_cls.id_allocator = self.id_allocator
        handler_cls.scanner = self.scanner
        handler_cls.asset_renumberer = self.asset_renumberer
        handler_cls.param_builder = self.param_builder
        handler_cls.backup_manager = self.backup_manager
        handler_cls.manifest_store = self.manifest_store
        handler_cls.regulation_manager = self.regulation_manager
        handler_cls.ui_root = self.base_dir / "ui"
        handler_cls.data_root = self.base_dir / "data"

        port = self.config.port
        self.server = HTTPServer(("127.0.0.1", port), handler_cls)
        system_logger.info(f"LootForge server online at http://127.0.0.1:{port}", source="Server")
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            system_logger.info("Stopping LootForge server...", source="Server")
            self.server.server_close()
