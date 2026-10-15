"""The writable import fields shared with RegTool's PARAM conversion contract."""

from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET


_DEFINITIONS = {"custom_skills": "SwordArtsParam", "custom_behaviors": "BehaviorParam", "custom_attacks": "AtkParam"}
_WRITABLE_TYPES = {"s8", "u8", "s16", "u16", "s32", "u32", "b32", "f32", "f64", "fixstr", "fixstrW"}


@lru_cache(maxsize=12)
def _schema_fields(path, modified_ns):
    """Cache the native schema, excluding dummy8 padding that RegTool never applies."""
    fields = set()
    for element in ET.parse(path).getroot().findall("./Fields/Field"):
        parts = element.attrib["Def"].split()
        if parts[0] in _WRITABLE_TYPES:
            fields.add(parts[1].split(":", 1)[0].split("[", 1)[0].casefold())
    return frozenset(fields)


def writable_import_fields(category):
    """Return actual writable field names for one imported parameter category."""
    path = Path(__file__).resolve().parents[1] / "tools/vendor/Paramdex/ER/Defs" / (_DEFINITIONS[category] + ".xml")
    return _schema_fields(path, path.stat().st_mtime_ns)


def applied_fields(row, field_names):
    """Compare runtime field values independently of extraction names, padding and unused fields."""
    return {name.casefold(): value for name, value in row.get("fields", {}).items() if name.casefold() in field_names}
