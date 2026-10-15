"""
Patch Orchestrator for LootForge Qt GUI.
Executes the mod forging, parameter injection, Diablo loot generation, and file deployment pipeline.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from PySide6.QtWidgets import QMessageBox
except (ImportError, Exception):
    from PyQt6.QtWidgets import QMessageBox

from src.logger import system_logger


class PatchOrchestrator:
    """
    Coordinates end-to-end patch generation, backup creation, and asset deployment.
    """

    @classmethod
    def create_backup(cls, window: Any) -> None:
        """Creates backup of regulation.bin."""
        reg_path = window.active_reg_input.text().strip() or os.path.join(window.config.game_directory, "regulation.bin")
        try:
            if not Path(reg_path).exists():
                raise FileNotFoundError(f"Regulation file not found: {reg_path}")
            rec = window.backup_manager.create_backup(reg_path)
            QMessageBox.information(window, "Backup Created", f"Successfully created backup:\n{rec.backup_file_name}")
        except Exception as e:
            QMessageBox.critical(window, "Backup Error", f"Failed to create backup: {e}")

    @classmethod
    def restore_backup(cls, window: Any) -> None:
        """Restores pristine regulation.bin and message files from backups."""
        reg_path = window.active_reg_input.text().strip() or os.path.join(window.config.game_directory, "regulation.bin")
        reply = QMessageBox.question(window, "Confirm Restore", "Restore pristine regulation.bin and message files from the latest backups?")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                window.backup_manager.restore_latest_backup(reg_path)
                target_p = Path(reg_path)
                for lang in ["engUS", "engus"]:
                    for fname in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx", "item_dlc01.msgbnd.dcx"]:
                        mf = target_p.parent / "msg" / lang / fname
                        if window.backup_manager.list_backups_for_file(fname):
                            try:
                                window.backup_manager.restore_latest_backup_for_file(str(mf))
                            except Exception:
                                pass
                QMessageBox.information(window, "Restore Complete", "Pristine regulation.bin and message files restored successfully.")
            except Exception as e:
                QMessageBox.critical(window, "Restore Error", f"Restore failed: {e}")

    @classmethod
    def uninstall_mods(cls, window: Any) -> None:
        """Rolls back all injected standalone mods, restores regulation/msg files, and cleans parts."""
        reply = QMessageBox.question(
            window,
            "Confirm Rollback",
            "Comprehensively roll back all injected standalone mods, restore original regulation.bin and msg files, and remove deployed parts?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                active_input = window.active_reg_input.text().strip()
                result = window.regulation_manager.rollback_all(
                    backup_manager=window.backup_manager,
                    manifest_store=window.manifest_store,
                    target_reg_path=active_input,
                    output_dir=window.config.output_directory,
                    asset_renumberer=window.asset_renumberer
                )
                restored_cnt = len(result["restored_files"])
                removed_cnt = len(result["removed_files"])
                details = f"Restored {restored_cnt} file(s) and removed {removed_cnt} staged/deployed file(s)."
                if result["errors"]:
                    details += f"\n\nWarnings/Errors:\n" + "\n".join(result["errors"])

                QMessageBox.information(window, "Rollback Complete", f"Rollback finished cleanly!\n\n{details}")
                window._scan_mods()
            except Exception as e:
                QMessageBox.critical(window, "Rollback Error", f"Uninstall/rollback failed: {e}")

    @classmethod
    def forge_mods_dialog(cls, window: Any) -> None:
        """Validates inputs and executes forging pipeline with interactive feedback."""
        if not window.scanned_sets and not window.config.diablo_use_vanilla_base_items and not window.config.diablo_inject_vanilla_stats:
            QMessageBox.warning(window, "No Mods", "No mod sets detected in input_mods, and vanilla item injection is not enabled.")
            return

        active_input = window.active_reg_input.text().strip()

        try:
            window._recalculate_distribution()
            window._ensure_all_deep_introspected()
            result = cls.forge_mods(
                base_dir=window.base_dir,
                config=window.config,
                config_path=window.config_path,
                scanned_sets=window.scanned_sets,
                drop_configs=window.drop_configs,
                global_multiplier_percent=window.global_multiplier_percent,
                active_input=active_input,
                regulation_manager=window.regulation_manager,
                backup_manager=window.backup_manager,
                asset_renumberer=window.asset_renumberer,
                param_builder=window.param_builder,
                manifest_store=window.manifest_store,
                knowledge_base=window.knowledge_base,
                id_allocator=window.id_allocator,
                distributor=window.distributor
            )
            window.active_reg_input.setText(str(result["target_reg"]))
            QMessageBox.information(window, "Forge Complete", result["message"])
        except Exception as e:
            system_logger.error(f"Forge failed: {e}", source="Forge")
            QMessageBox.critical(window, "Forge Error", f"Forge failed: {e}")

    @classmethod
    def forge_mods(
        cls,
        base_dir: Path,
        config: Any,
        config_path: str,
        scanned_sets: list,
        drop_configs: list,
        global_multiplier_percent: float,
        active_input: str,
        regulation_manager: Any,
        backup_manager: Any,
        asset_renumberer: Any,
        param_builder: Any,
        manifest_store: Any,
        knowledge_base: Any,
        id_allocator: Any,
        distributor: Any
    ) -> Dict[str, Any]:
        """
        Executes the forging and injection pipeline.
        Returns result dict with counts, paths, and status message.
        """
        if config.game_directory:
            regulation_manager.backup_game_assets(config.game_directory)

        source_reg = regulation_manager.resolve_source_regulation(
            active_path=active_input,
            game_dir=config.game_directory,
            output_dir=config.output_directory
        )
        if not source_reg or not source_reg.exists():
            raise FileNotFoundError("Could not find a valid Elden Ring regulation.bin to read from!")

        # Real-time discovery of all chests and bosses in source_reg (supporting any overhaul mod)
        try:
            snapshot_path = base_dir / "data" / "world_snapshot.json"
            regulation_manager.introspect_world(source_reg, output_json=snapshot_path)
            from src.knowledge_base import VanillaKnowledgeBase
            knowledge_base = VanillaKnowledgeBase.from_data_dir(str(base_dir / "data"))
        except Exception as ie:
            system_logger.warning(f"Real-time world introspection notice: {ie}", source="PatchOrchestrator")

        from src.variant_capacity import calculate_capacity, clamp_variants
        param_builder.kb = knowledge_base
        capacity_specs = [param_builder.build_patch_spec(mod, include_custom_art=False)
                          for mod in scanned_sets if getattr(mod, "is_enabled", True)]
        capacity = calculate_capacity(regulation_manager.equipment_row_counts(source_reg), capacity_specs,
                                      knowledge_base, config.diablo_use_vanilla_base_items)
        if clamp_variants(config, capacity):
            config.save(config_path)
            system_logger.info(f"Variants capped at {capacity.maximum} for this selection and regulation.", source="Forge")

        target_reg = regulation_manager.resolve_target_regulation(
            active_path=active_input,
            output_dir=config.output_directory,
            game_dir=config.game_directory
        )

        # Pre-backup or track existing msg files in target directory
        created_msg_files = []
        backed_up_files = {}
        seen_msg_paths = set()
        languages = {"engUS", "engus"}
        message_root = target_reg.parent / "msg"
        if message_root.exists():
            languages.update(path.name for path in message_root.iterdir() if path.is_dir())
        for lang in sorted(languages):
            lang_dir = target_reg.parent / "msg" / lang
            for fname in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx", "item_dlc01.msgbnd.dcx"]:
                mf = lang_dir / fname
                msg_key = os.path.normcase(str(mf.resolve()))
                if msg_key in seen_msg_paths:
                    continue
                seen_msg_paths.add(msg_key)
                if mf.exists():
                    bak_rec = backup_manager.create_file_backup(str(mf), category="msg")
                    backed_up_files[str(mf)] = bak_rec.backup_file_name
                else:
                    created_msg_files.append(str(mf))

        infusion_state = target_reg.parent / "lootforge_diablo_fields.json"
        if infusion_state.exists():
            state_backup = backup_manager.create_file_backup(str(infusion_state), category="diablo")
            backed_up_files[str(infusion_state)] = state_backup.backup_file_name
        elif config.diablo_loot_enabled and config.diablo_inject_vanilla_stats:
            created_msg_files.append(str(infusion_state))

        text_state = target_reg.parent / "lootforge_diablo_texts.json"
        if text_state.exists():
            text_backup = backup_manager.create_file_backup(str(text_state), category="diablo")
            backed_up_files[str(text_state)] = text_backup.backup_file_name
        elif config.diablo_loot_enabled and config.diablo_inject_vanilla_stats:
            created_msg_files.append(str(text_state))

        event_file = target_reg.parent / "event" / "common.emevd.dcx"
        if event_file.exists():
            event_backup = backup_manager.create_file_backup(str(event_file), category="event")
            backed_up_files[str(event_file)] = event_backup.backup_file_name
        elif config.diablo_loot_enabled and config.diablo_triggered_effects:
            created_msg_files.append(str(event_file))

        patch_specs = []
        injected_count = 0
        diablo_total_variants = 0

        diablo_gen = None
        if config.diablo_loot_enabled:
            from src.diablo_generator import DiabloLootGenerator
            diablo_gen = DiabloLootGenerator(
                seed=config.diablo_seed, knowledge_base=knowledge_base,
                randomize_weapon_skills=config.diablo_randomize_weapon_skills,
                balance_weapon_skills_by_progression=config.diablo_balance_weapon_skills_by_progression,
                stats_multiplier=config.stats_multiplier, price_multiplier=config.price_multiplier,
                progression_scaling=config.diablo_progression_scaling,
                extra_passives=config.diablo_extra_passives,
                triggered_effects=config.diablo_triggered_effects,
                auras_enabled=config.diablo_auras_enabled
            )

        # Generate and validate the patch before staging any assets.
        input_p = Path(config.input_directory)
        if not input_p.is_absolute():
            input_p = base_dir / input_p
        if len(scanned_sets) != len(drop_configs):
            raise ValueError("Mod sets and loot settings do not match. Scan the mods again.")
        for s, cfg in zip(scanned_sets, drop_configs):
            if not getattr(s, "is_enabled", True):
                continue
            s.import_custom_moveset = getattr(config, "import_custom_skills_movesets", True) and getattr(cfg, "import_custom_art", True)
            if s.loot_target:
                s.loot_target.chance_or_cost = distributor.calculate_final_rate(cfg.user_rate, global_multiplier_percent)

            base_spec = param_builder.build_patch_spec(s)
            if diablo_gen and config.diablo_loot_enabled and config.diablo_variants_per_item >= 1:
                variants = diablo_gen.generate_variants_for_spec(base_spec, variants_per_item=config.diablo_variants_per_item)
                patch_specs.extend(variants)
                diablo_total_variants += len(variants)
            else:
                patch_specs.append(base_spec)

            injected_count += 1

        # Phase 2: Inject vanilla base items for distribution if enabled
        if diablo_gen and config.diablo_use_vanilla_base_items:
            vanilla_dist_specs = diablo_gen.generate_vanilla_base_distribution_specs(
                knowledge_base=knowledge_base, id_allocator=id_allocator,
                variants_per_item=config.diablo_variants_per_item if config.diablo_loot_enabled else 1
            )
            patch_specs.extend(vanilla_dist_specs)
            diablo_total_variants += len(vanilla_dist_specs)
            injected_count += len(vanilla_dist_specs)
            system_logger.info(f"Generated {len(vanilla_dist_specs)} procedural relics from vanilla base items.", source="PatchOrchestrator")

        if diablo_gen and config.diablo_inject_vanilla_stats:
            patch_specs.extend(diablo_gen.generate_vanilla_stat_injections(knowledge_base))

        patch_specs = regulation_manager.prepare_patch_specs(patch_specs, source_reg)
        if target_reg.exists():
            backup_manager.create_backup(str(target_reg))

        # Stage beside the selected regulation, including an external mod-manager profile.
        from src.asset_renumberer import AssetRenumberer
        deployer = AssetRenumberer(str(target_reg.parent))
        staged_by_set = deployer.stage_all_mod_sets(str(input_p), scanned_sets)
        all_deployed_files = []
        for s in scanned_sets:
            if not getattr(s, "is_enabled", True):
                continue
            staged = staged_by_set.get(s.set_id, [])
            all_deployed_files.extend(str(target_reg.parent / path) for path in staged)

        # Phase 3: Single-pass in-memory regulation patch
        patch_result = regulation_manager.execute_patch(
            specs=patch_specs,
            source_reg=source_reg,
            target_reg=target_reg,
            game_dir=config.game_directory,
            boss_loot_pools_enabled=getattr(config, "boss_loot_pools_enabled", True),
            boss_weapons_per_pool=getattr(config, "boss_weapons_per_pool", 3),
            chest_loot_pools_enabled=getattr(config, "chest_loot_pools_enabled", True),
            chest_min_items=getattr(config, "chest_min_items", 1),
            chest_max_items=getattr(config, "chest_max_items", 4),
            sweep_vanilla_items=False,
            randomize_skills=config.diablo_randomize_weapon_skills,
            seed=config.diablo_seed
        )

        for s in scanned_sets:
            if getattr(s, "is_enabled", True):
                manifest_store.record_set(s, staged_by_set.get(s.set_id, []), save_now=False)

        from src.skill_moveset_importer import SkillMovesetImporter
        moveset_importer = SkillMovesetImporter(base_dir)
        for s in scanned_sets:
            if getattr(s, "is_enabled", True) and s.is_weapon and s.import_custom_moveset and s.skill_moveset:
                all_deployed_files.extend(moveset_importer.deploy_moveset_assets(s, input_p, target_reg.parent, backup_manager))
                backed_up_files.update(moveset_importer.last_backed_up_files)

        # Phase 4: Record deployment manifest in ONE single disk write
        manifest_store.record_deployment(
            target_regulation_path=str(target_reg),
            deployed_files=all_deployed_files,
            created_msg_files=created_msg_files,
            backed_up_files=backed_up_files,
            save_now=True
        )

        config.active_regulation_path = str(target_reg)
        config.save(config_path)

        output_dir = target_reg.parent
        parts_deployed = len(all_deployed_files)
        file_size_mb = round(patch_result["target_size_bytes"] / (1024 * 1024), 2)
        diablo_info = f"⚡ Diablo ARPG: {diablo_total_variants} procedural relics generated!\n" if diablo_total_variants > 0 else ""
        custom_skills_count = sum(1 for s in scanned_sets if getattr(s, "import_custom_moveset", True) and s.skill_moveset and s.skill_moveset.has_custom_skill)
        custom_movesets_count = sum(1 for s in scanned_sets if getattr(s, "import_custom_moveset", True) and s.skill_moveset and s.skill_moveset.has_custom_moveset)
        art_info = f"⚔ Custom Art: {custom_skills_count} skill(s) & {custom_movesets_count} moveset(s) ported!\n" if (custom_skills_count > 0 or custom_movesets_count > 0) else ""

        msg = (
            f"Successfully forged and injected {injected_count} standalone mod set(s)!\n\n"
            f"{diablo_info}"
            f"{art_info}"
            f"✅ Regulation: '{target_reg}' ({file_size_mb} MB)\n"
            f"✅ Parts Deployed: {parts_deployed} files to {output_dir / 'parts'}\n\n"
            f"Ready to launch with Mod Engine 2 or your mod manager!"
        )

        return {
            "success": True,
            "target_reg": target_reg,
            "file_size_mb": file_size_mb,
            "parts_deployed": parts_deployed,
            "injected_count": injected_count,
            "diablo_variants": diablo_total_variants,
            "message": msg
        }
