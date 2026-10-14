"""
Server Forge Service for LootForge HTTP API.
Coordinates staging, real-time world introspection, param patching, and asset deployment.
Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from pathlib import Path
from typing import Dict, Any, List
from src.logger import system_logger
from src.models import LootDistributionType, LootTarget


class ServerForgeService:
    """Executes the full forge lifecycle for HTTP REST requests."""

    @staticmethod
    def execute_forge(handler: Any, sets_data: List[Dict[str, Any]], body: Dict[str, Any]) -> Dict[str, Any]:
        system_logger.info(f"Starting forge run for {len(sets_data)} mod set(s)...", source="Forge")

        detected_map = {
            s.set_id: s for s in handler.scanner.scan_directory(handler.config.input_directory)
        }

        injected_records = []
        all_specs = []
        forged_mod_sets = []
        for entry in sets_data:
            set_id = entry.get("set_id")
            if set_id not in detected_map:
                continue

            mod_set = detected_map[set_id]
            alloc = handler.id_allocator.allocate(mod_set.set_id)
            mod_set.allocation = alloc

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

            staged_files = handler.asset_renumberer.stage_mod_set(handler.config.input_directory, mod_set)
            patch_spec = handler.param_builder.build_patch_spec(mod_set)
            all_specs.append(patch_spec)

            record = handler.manifest_store.record_set(mod_set, staged_files, save_now=False)
            injected_records.append(record)
            forged_mod_sets.append(mod_set)

        active_reg = body.get("path") or handler.config.active_regulation_path or ""
        source_reg = handler.regulation_manager.resolve_source_regulation(
            active_path=active_reg,
            game_dir=handler.config.game_directory,
            output_dir=handler.config.output_directory
        )

        reg_result = None
        target_reg = None
        if source_reg and source_reg.exists():
            # Real-time world introspection of source regulation (supporting any overhaul mod)
            try:
                snapshot_path = handler.base_dir / "data" / "world_snapshot.json"
                handler.regulation_manager.introspect_world(source_reg, output_json=snapshot_path)
                from src.knowledge_base import VanillaKnowledgeBase
                handler.knowledge_base = VanillaKnowledgeBase.from_data_dir(str(handler.base_dir / "data"))
            except Exception as ie:
                system_logger.warning(f"Real-time world introspection notice: {ie}", source="Forge")

            target_reg = handler.regulation_manager.resolve_target_regulation(
                active_path=active_reg,
                output_dir=handler.config.output_directory,
                game_dir=handler.config.game_directory
            )

            if target_reg.exists():
                try:
                    handler.backup_manager.create_backup(str(target_reg))
                except Exception as be:
                    system_logger.warning(f"Auto-backup notice: {be}", source="Forge")

            created_msg_files = []
            backed_up_files = {}
            for lang in ["engUS", "engus"]:
                lang_dir = target_reg.parent / "msg" / lang
                for fname in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx", "item_dlc01.msgbnd.dcx"]:
                    mf = lang_dir / fname
                    if mf.exists():
                        try:
                            bak_rec = handler.backup_manager.create_file_backup(str(mf), category="msg")
                            backed_up_files[str(mf)] = bak_rec.backup_file_name
                        except Exception as me:
                            system_logger.warning(f"Msg backup notice ({mf}): {me}", source="Forge")
                    else:
                        created_msg_files.append(str(mf))

            reg_result = handler.regulation_manager.execute_patch(
                all_specs, source_reg, target_reg, game_dir=handler.config.game_directory
            )
            handler.config.active_regulation_path = str(target_reg)
            handler.config.save()

            parts_deployed = 0
            try:
                input_dir = Path(handler.config.input_directory)
                if not input_dir.is_absolute():
                    input_dir = handler.base_dir / input_dir
                parts_deployed = handler.regulation_manager.deploy_parts(
                    mod_sets=forged_mod_sets,
                    input_base_dir=input_dir,
                    output_dir=target_reg.parent,
                    backup_manager=handler.backup_manager
                )
                system_logger.info(f"Deployed {parts_deployed} parts files to {target_reg.parent / 'parts'}", source="Forge")
            except Exception as pe:
                system_logger.warning(f"Parts deployment notice: {pe}", source="Forge")

            deployed_parts = getattr(handler.regulation_manager, "last_deployed_files", [])
            parts_backed_up = getattr(handler.regulation_manager, "last_backed_up_files", {})
            if parts_backed_up:
                backed_up_files.update(parts_backed_up)

            handler.manifest_store.record_deployment(
                target_regulation_path=str(target_reg),
                deployed_files=deployed_parts,
                created_msg_files=created_msg_files,
                backed_up_files=backed_up_files
            )

        if reg_result:
            fmg_verification = reg_result.get("fmg_verification", {})
            if fmg_verification:
                if fmg_verification.get("verified"):
                    system_logger.info(f"FMG verification PASSED: {len(fmg_verification.get('regulation_items', []))} items verified", source="Forge")
                else:
                    missing = fmg_verification.get("missing_in_fmg", [])
                    system_logger.warning(f"FMG verification FAILED: {len(missing)} items missing from FMG: {missing}", source="Forge")
                    for err in fmg_verification.get("errors", []):
                        system_logger.error(f"FMG verification error: {err}", source="Forge")

        system_logger.info(f"Forge successfully completed! {len(injected_records)} set(s) injected.", source="Forge")
        return {
            "success": True,
            "injected_count": len(injected_records),
            "sets": [r.set_id for r in injected_records],
            "target_regulation": str(target_reg) if target_reg else None
        }
