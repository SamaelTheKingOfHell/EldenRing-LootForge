"""
Knowledge Base loader service for LootForge.
Loads static models/routes data and ingests live world snapshots.
Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.logger import system_logger


class KnowledgeLoader:
    """Loads and merges vanilla data catalogs and smart world snapshots."""

    @staticmethod
    def load_data(data_dir: str = "data") -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Loads static JSON files and merges live world snapshot if available."""
        p = Path(data_dir)
        models_file = p / "vanilla_models.json"
        routes_file = p / "loot_routes.json"

        models_data: Dict[str, Any] = {}
        routes_data: Dict[str, Any] = {}

        if models_file.exists():
            with open(models_file, "r", encoding="utf-8") as f:
                models_data = json.load(f)
        else:
            system_logger.warning(f"Models file not found: {models_file}", source="KnowledgeBase")

        if routes_file.exists():
            with open(routes_file, "r", encoding="utf-8") as f:
                routes_data = json.load(f)
        else:
            system_logger.warning(f"Loot routes file not found: {routes_file}", source="KnowledgeBase")

        snapshot_file = p / "world_snapshot.json"
        if snapshot_file.exists():
            try:
                with open(snapshot_file, "r", encoding="utf-8") as f:
                    snap = json.load(f)
                KnowledgeLoader.ingest_discovered_snapshot(snap, models_data, routes_data)
            except Exception as e:
                system_logger.warning(f"Could not load world snapshot: {e}", source="KnowledgeBase")

        if not models_data.get("weapons") and models_data.get("_discovered_weapons"):
            models_data["weapons"] = models_data["_discovered_weapons"]
        if not models_data.get("protectors") and models_data.get("_discovered_protectors"):
            models_data["protectors"] = models_data["_discovered_protectors"]
        if not models_data.get("accessories") and models_data.get("_discovered_accessories"):
            models_data["accessories"] = models_data["_discovered_accessories"]

        return models_data, routes_data

    @staticmethod
    def ingest_discovered_snapshot(
        snap: Dict[str, Any],
        models_data: Dict[str, Any],
        routes_data: Dict[str, Any]
    ) -> None:
        """Parses and ingests a smart discovery world snapshot into models and routes catalogs."""
        # Ingest discovered weapons
        disc_weps: Dict[str, Any] = {}
        for w in snap.get("Weapons", []):
            wid = str(w.get("Id", ""))
            mid = str(w.get("ModelId", ""))
            if wid:
                entry = {
                    "name": w.get("Name", f"Weapon {wid}"),
                    "baseParamId": w.get("Id"),
                    "defaultRoute": "merchant_shop",
                    "progressionTier": w.get("Tier", 1),
                    "modelId": w.get("ModelId"),
                    "wepType": w.get("WepType", 0)
                }
                disc_weps[wid] = entry
                if mid and (mid not in disc_weps or w.get("IsBaseWeapon")):
                    disc_weps[mid] = entry
        models_data["_discovered_weapons"] = disc_weps

        # Ingest discovered protectors
        disc_prots: Dict[str, Any] = {}
        for prot in snap.get("Protectors", []):
            pid = str(prot.get("Id", ""))
            mid = str(prot.get("ModelId", ""))
            slot_name = prot.get("SlotName", "Armor")
            if pid:
                entry = {
                    "name": prot.get("Name", f"Armor {pid}"),
                    "baseParamId": prot.get("Id"),
                    "defaultRoute": "enemy_drop",
                    "progressionTier": prot.get("Tier", 1),
                    "modelId": prot.get("ModelId"),
                    "pieces": {}
                }
                disc_prots[pid] = entry
                if mid:
                    if mid not in disc_prots:
                        disc_prots[mid] = {
                            "name": prot.get("Name", f"Set {mid}"),
                            "baseParamId": prot.get("Id"),
                            "defaultRoute": "enemy_drop",
                            "progressionTier": prot.get("Tier", 1),
                            "modelId": prot.get("ModelId"),
                            "pieces": {}
                        }
                    disc_prots[mid]["pieces"][slot_name] = prot.get("Id")
        models_data["_discovered_protectors"] = disc_prots

        # Ingest discovered accessories
        disc_accs: Dict[str, Any] = {}
        for acc in snap.get("Accessories", []):
            aid = str(acc.get("Id", ""))
            if aid:
                disc_accs[aid] = {
                    "name": acc.get("Name", f"Talisman {aid}"),
                    "baseParamId": acc.get("Id"),
                    "defaultRoute": "enemy_drop",
                    "progressionTier": acc.get("Tier", 1),
                    "iconId": acc.get("IconId", 18000)
                }
        models_data["_discovered_accessories"] = disc_accs

        # Ingest discovered boss lots
        disc_bosses: List[Dict[str, Any]] = []
        for bl in snap.get("BossLots", []):
            lot_id = bl.get("LotId")
            if lot_id:
                disc_bosses.append({
                    "id": f"boss_lot_{lot_id}",
                    "name": bl.get("Name", f"Boss Lot {lot_id}"),
                    "boss": bl.get("Name", f"Boss Lot {lot_id}"),
                    "lotParamId": lot_id,
                    "progressionTier": bl.get("Tier", 1),
                    "defaultCost": 30000
                })
        routes_data["_discovered_boss_lots"] = disc_bosses

        # Ingest ALL discovered chests and map pickups (Vanilla, DLC, Modded)
        disc_chests: List[Dict[str, Any]] = []
        for c in snap.get("Chests", []):
            lot_id = c.get("LotId")
            if lot_id:
                disc_chests.append({
                    "id": f"chest_lot_{lot_id}",
                    "name": c.get("Name", f"Chest Lot {lot_id}"),
                    "lotParamId": lot_id,
                    "progressionTier": c.get("Tier", 1),
                    "baseItemId": c.get("BaseItemId", 0),
                    "category": c.get("Category", 0)
                })
        routes_data["_discovered_chests"] = disc_chests

        system_logger.info(
            f"Smart Discovery: Ingested live snapshot ({len(disc_weps)} weapons, "
            f"{len(disc_prots)} protectors, {len(disc_bosses)} boss lots, "
            f"{len(disc_chests)} chests).",
            source="KnowledgeBase"
        )
