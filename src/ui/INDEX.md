# LootForge UI Components

Modular UI presentation components, styling definitions, parameter schema, and modal dialogs supporting the desktop Qt application and web interfaces.
Adheres to `[CS-MODULAR]` and `[CS-GRANULARITY]`.

## Modules

| Module | Component | Purpose |
| :--- | :--- | :--- |
| `INDEX.md` | - | Index and documentation for UI modules. |
| `theme.py` | `DARK_SOULS_QSS` | Dark Souls / Elden Ring themed QSS stylesheet and color palette constants. |
| `param_schema.py` | `ParamSchema` | Typed parameter metadata descriptors (`ParamType`, `ParamPurpose`, bounds, options) decoupling definitions from layouts. |
| `param_widget_factory.py` | `ParamWidgetFactory` | Data-driven factory automatically constructing typed controls and styled cards by purpose. |
| `loot_modal.py` | `LootReviewModal` | Dedicated interactive modal dialog for searching, inspecting, and customizing item drop rates, mystery mode, and custom weapon skill/moveset toggles and badges. |
