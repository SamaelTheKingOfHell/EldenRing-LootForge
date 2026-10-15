"""Build reproducible native integration inputs from the local discovery snapshot.

The high-rarity fixtures deliberately cover every aura and all combat categories;
they are controlled coverage inputs, not a sample of ordinary drop frequency.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.diablo_affixes import RarityTier
from src.diablo_generator import DiabloLootGenerator
from src.diablo_vanilla_stat_injector import VanillaStatInjector
from src.knowledge_base import VanillaKnowledgeBase


def build():
    kb = VanillaKnowledgeBase.from_data_dir(str(ROOT / "data"))
    generator = DiabloLootGenerator(seed=94715, knowledge_base=kb,
        extra_passives=True, triggered_effects=True, auras_enabled=True)
    specs = generator.generate_vanilla_stat_injections()
    weapons = list(VanillaStatInjector.catalog(kb, "weapons").values())
    shield = next(row["baseParamId"] for row in weapons if row.get("wepType") in (65, 67, 69))
    themes = ("fire", "lightning", "glintstone", "holy", "frost", "blood", "poison", "rot", "renewal")
    for i in range(800):
        weapon, guarding = i % 3 != 0, i % 3 == 2
        rarity = RarityTier.LEGENDARY if i % 2 else RarityTier.MYTHIC
        affixes = generator.roll_affixes(rarity, weapon, tier=i % 4 + 1, is_shield=guarding)
        fields = {}
        generator.apply_affixes_to_equipment(fields, affixes, is_weapon=weapon)
        specs.append({"set_id": f"coverage_{i}", "equip_params": [{
            "param_table": "EquipParamWeapon" if weapon else "EquipParamProtector",
            "new_param_id": shield if guarding else 2020000 if weapon else 10000,
            "field_updates": fields}]})
    index = 0
    for spec in specs:
        for ep in spec["equip_params"]:
            ep["base_clone_id"] = ep["new_param_id"]
            ep["new_param_id"] = 180000000 + index
            ep.pop("update_existing", None)
            ep.pop("diablo_infusion_family", None)
            if ep["param_table"] != "EquipParamAccessory":
                ep["field_updates"]["_lf_diablo_aura"] = themes[index % len(themes)]
            index += 1
    return specs


if __name__ == "__main__":
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    specs = build()
    output.write_text(json.dumps(specs), encoding="utf-8")
    print(f"Wrote {len(specs)} native coverage specifications to {output}")
