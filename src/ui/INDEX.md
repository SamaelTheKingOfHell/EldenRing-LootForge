# LootForge UI Components

Modular UI presentation components, styling definitions, parameter schema, layout builders, patch orchestrators, and modal dialogs supporting the desktop Qt application and web interfaces.
Adheres to `[CS-MODULAR]` and `[CS-GRANULARITY]`.

## Modules

| Module | Component | Purpose |
| :--- | :--- | :--- |
| `INDEX.md` | - | Index and documentation for UI modules. |
| `theme.py` | `DARK_SOULS_QSS` | Dark Souls / Elden Ring themed QSS stylesheet and color palette constants. |
| `param_schema.py` | `ParamSchema` | Typed parameter metadata descriptors (`ParamType`, `ParamPurpose`, bounds, options) decoupling definitions from layouts. |
| `param_widget_factory.py` | `ParamWidgetFactory` | Data-driven factory automatically constructing typed controls and styled cards by purpose. |
| `loot_modal.py` | `LootReviewModal` | Dedicated interactive modal dialog for searching, inspecting, and customizing item drop rates, mystery mode, and custom weapon skill/moveset toggles and badges. |
| `main_window_builder.py` | `MainWindowBuilder` | Constructs GUI layout hierarchy, setting cards, splitters, and dev console drawer. |
| `patch_orchestrator.py` | `PatchOrchestrator` | Coordinates end-to-end patch generation, backup creation, forging pipeline, and asset deployment. |
| `mod_scanner_service.py` | `ModScannerService` | Handles mod directory scanning, ID allocation, moveset extraction, and loot distribution calculation. |


## Patcher performance and capacity

- `variant_capacity_controller.py`: Debounced background Qt capacity calculation and dynamic variants limit.
