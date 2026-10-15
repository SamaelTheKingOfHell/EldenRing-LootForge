"""Reproducible local benchmark; writes only under scratch/performance, never the active mod profile.

Run: python tests/benchmark_patcher.py --before-dir scratch/regtool-before
The before directory must contain a preserved, runnable pre-change RegTool build.
"""

import argparse
import gc
import json
import subprocess
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.diablo_generator import DiabloLootGenerator


def run():
    """Compare identical native patch inputs and variant generation with a shared imported payload."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-dir", type=Path, required=True)
    parser.add_argument("--before-ref", default="83d6fa0")
    parser.add_argument("--rows", type=int, default=4000)
    args = parser.parse_args()
    output = ROOT / "scratch/performance"
    output.mkdir(parents=True, exist_ok=True)
    source = next(iter(sorted((ROOT / "backups").glob("regulation.bin.bak_*"))), None)
    if source is None:
        raise SystemExit("A real backed-up regulation is required.")
    defs = ROOT / "tools/vendor/Paramdex/ER/Defs"
    spec = [{"equip_params": [{"param_table": "EquipParamAccessory", "new_param_id": 100000000 + i,
                              "base_clone_id": 1000, "row_name": "[LootForge] Benchmark",
                              "field_updates": {"sortId": 100000000 + i, "weight": 0.5, "sellValue": 100}}],
             "loot_distribution": {"type": "enemy_drop", "target_id": "380000000", "drop_rate_percent": 20,
                                   "awarded_items": [100000000 + i]}} for i in range(args.rows)]
    spec_path = output / "spec.json"
    spec_path.write_text(json.dumps(spec, separators=(",", ":")), encoding="utf-8")
    results = {"source": source.name, "rows": args.rows, "scope": "controlled real-regulation patch plus vanilla infusion"}
    for label, executable in (("before", args.before_dir / "RegTool.exe"),
                              ("after", ROOT / "tools/RegTool/bin/Release/net9.0/RegTool.exe")):
        target = output / (label + "-combined") / "regulation.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        command = [str(executable.resolve()), "patch", "--input", str(source), "--output", str(target),
                   "--defs", str(defs), "--spec", str(spec_path)]
        if label == "after":
            command += ["--sweep-vanilla", "true", "--randomize-skills", "false"]
        started = time.perf_counter()
        response = subprocess.run(command, capture_output=True, text=True, check=True)
        log = response.stdout
        if label == "before":
            response = subprocess.run([str(executable.resolve()), "sweep-vanilla", "--input", str(target),
                                       "--output", str(target), "--defs", str(defs), "--randomize-skills", "false"],
                                      capture_output=True, text=True, check=True)
            log += response.stdout
        results[label] = {"combined_seconds": round(time.perf_counter() - started, 3)}
        (output / (label + "-combined.log")).write_text(log, encoding="utf-8")
        subprocess.run([str(executable.resolve()), "verify", "--input", str(target)], capture_output=True, check=True)

    old_source = subprocess.run(["git", "show", args.before_ref + ":src/diablo_variant_builder.py"],
                                cwd=ROOT, capture_output=True, text=True, check=True).stdout
    old_module = types.ModuleType("before_variant_builder")
    exec(compile(old_source, "before_variant_builder.py", "exec"), old_module.__dict__)
    from src.diablo_variant_builder import DiabloVariantBuilder
    base = {"set_id": "payload-benchmark", "equip_params": [{"param_table": "EquipParamWeapon", "new_param_id": 9000000,
             "field_updates": {}}], "fmg_texts": [{"item_id": 9000000, "name": "Sword", "caption": "Lore"}],
            "custom_behaviors": [{"id": i, "fields": {f"field_{j}": j for j in range(10)}} for i in range(1000)]}
    for label, builder in (("before", old_module.DiabloVariantBuilder), ("after", DiabloVariantBuilder)):
        gc.collect()
        started = time.perf_counter()
        variants = builder.generate_variants(DiabloLootGenerator(seed=42), base, 250)
        seconds = time.perf_counter() - started
        size = sum(len(json.dumps(s, separators=(",", ":")).encode("utf-8")) for s in variants)
        results[label].update(generation_seconds=round(seconds, 4), serialized_bytes=size)
        del variants
    (output / "combined-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run()
