"""
Data models for the LootForge Elden Ring modding engine.

Defines the core data transfer objects used across the mod scanner, ID allocator,
param builder, and manifest management subsystems.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class EquipmentSlot(str, Enum):
    """
    Armor and weapon equipment slots supported by Elden Ring.
    
    Why:
        Separates equipment categories to correctly populate EquipParamProtector
        or EquipParamWeapon and assign slot-specific model IDs.
    """
    HEAD = "head"
    BODY = "body"
    ARMS = "arms"
    LEGS = "legs"
    WEAPON = "weapon"
    UNKNOWN = "unknown"


class LootDistributionType(str, Enum):
    """
    Routing strategies for organically placing modded items in-game.
    
    Why:
        Enables seamless routing to Finger Reader Enia (Remembrance Boss Soul trade)
        or direct enemy mob drop tables.
    """
    BOSS_REMEMBRANCE = "boss_remembrance"
    ENEMY_DROP = "enemy_drop"
    MERCHANT_SHOP = "merchant_shop"
    MAP_PICKUP = "map_pickup"


class ProgressionTier(int, Enum):
    """
    Progression tiers governing Elden Ring world regions and item level scaling:
    1: Early Game - Limgrave, Stormhill, Weeping Peninsula, Stormveil Castle (Lv 1-35)
    2: Mid Game - Liurnia of the Lakes, Raya Lucaria, Caelid, Caria Manor, Siofra River (Lv 35-70)
    3: Late Game - Altus Plateau, Mt. Gelmir, Volcano Manor, Leyndell Royal Capital (Lv 70-100)
    4: Endgame - Mountaintops of the Giants, Consecrated Snowfield, Crumbling Farum Azula,
                 Haligtree/Elphael, Mohgwyn Palace, Ashen Capital (Lv 100-150+)
    """
    EARLY = 1
    MID = 2
    LATE = 3
    ENDGAME = 4


class AdditionType(int, Enum):
    """
    Enum 'Addition type' governing distribution algorithm:
    1: Random Addition - Places item on mobs randomly, EXCEPT for items that are not dropped,
       which are added randomly to bosses, shops, and transfusions.
    2: Standard Addition - Places them on the expected drop list, shop, or boss weapon transfusion.
    3: Test Mode (All Pools) - Distributes items across all loot pools (bosses, shops, enemies)
       with guaranteed drop rates to test and verify custom injection.
    """
    RANDOM_ADDITION = 1
    STANDARD_ADDITION = 2
    TEST_MODE = 3


class AntiDup(int, Enum):
    """
    Enum 'Anti dup' for 100% drop items:
    1: Boss rotation - Rotates 100% boss drops to another boss in matching progression tier
       (max 1 set per boss). Cascades immediately to high-value Chests After Boss, then wild mobs in tier.
    2: Everything in the wild - Disperses onto wild enemies strictly matching the item's progression tier.
    3: Chest after boss - Rotates 100% boss drops directly into high-value post-boss treasure chests
       matching the boss progression tier, bundled with multiple extra injections.
    """
    BOSS_ROTATION = 1
    EVERYTHING_IN_THE_WILD = 2
    CHEST_AFTER_BOSS = 3



@dataclass
class ItemDropConfig:
    """
    User-configurable drop rate specification for an item or set.
    """
    item_key: str
    name: str
    vanilla_rate: float
    user_rate: float
    is_spoiled: bool = False
    source_entity: str = ""
    is_100_percent: bool = False
    custom_skill_name: str = ""
    has_custom_moveset: bool = False
    import_custom_art: bool = True


@dataclass
class ModPartFile:
    """
    Represents an individual .partsbnd.dcx file extracted or discovered in an input mod.
    
    Example:
    ```python
    part = ModPartFile(
        file_name="bd_m_4000.partsbnd.dcx",
        relative_path="parts/bd_m_4000.partsbnd.dcx",
        slot=EquipmentSlot.BODY,
        target_model_id="4000",
        gender_variant="m",
        file_size_bytes=1048576
    )
    ```
    """
    file_name: str
    relative_path: str
    slot: EquipmentSlot
    target_model_id: str
    gender_variant: str = "m"  # 'm' or 'f'
    file_size_bytes: int = 0


@dataclass
class LootTarget:
    """
    Target destination where the custom standalone item will be rewarded to the player.
    
    Example:
    ```python
    target = LootTarget(
        route_type=LootDistributionType.BOSS_REMEMBRANCE,
        target_id="remembrance_starscourge",
        display_name="Remembrance of the Starscourge (General Radahn)",
        chance_or_cost=40000
    )
    ```
    """
    route_type: LootDistributionType
    target_id: str
    display_name: str
    chance_or_cost: float = 20.0  # Percentage drop chance or Rune cost


@dataclass
class StandaloneAllocation:
    """
    Allocated custom IDs for standalone conversion, preventing collision with vanilla game data.
    
    Example:
    ```python
    alloc = StandaloneAllocation(
        new_model_id="9001",
        new_equip_param_id=9001000,
        new_item_lot_id=9100001,
        marker_tag="[LootForge]"
    )
    ```
    """
    new_model_id: str
    new_equip_param_id: int
    new_item_lot_id: int
    marker_tag: str = "[LootForge]"


@dataclass
class SkillMovesetMetadata:
    """
    Metadata for custom skills (SwordArtsParam) and movesets (BehaviorParam_PC, animations)
    introspected and extracted from a weapon mod.
    """
    has_custom_skill: bool = False
    skill_id: int = 0
    skill_name: str = ""
    skill_caption: str = ""
    has_custom_moveset: bool = False
    behavior_variation_id: int = 0
    wepmotion_category: int = 0
    wepmotion_one_hand_id: int = 0
    wepmotion_both_hand_id: int = 0
    sp_atk_category: int = 0
    animation_banks: List[str] = field(default_factory=list)
    has_behavior_graph: bool = False
    has_sfx: bool = False
    has_action_scripts: bool = False
    custom_skills_spec: List[Dict[str, Any]] = field(default_factory=list)
    custom_behaviors_spec: List[Dict[str, Any]] = field(default_factory=list)
    custom_attacks_spec: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DetectedModSet:
    """
    A cohesive group of replacement parts comprising an armor set or weapon.
    
    Example:
    ```python
    mod_set = DetectedModSet(
        set_id="mod_berserk_armor",
        folder_or_archive_name="Dark_Knight_Berserk",
        target_model_id="4000",
        target_vanilla_name="Carian Knight Set",
        parts=[...],
        loot_target=LootTarget(...)
    )
    ```
    """
    set_id: str
    folder_or_archive_name: str
    target_model_id: str
    target_vanilla_name: str
    parts: List[ModPartFile] = field(default_factory=list)
    loot_target: Optional[LootTarget] = None
    allocation: Optional[StandaloneAllocation] = None
    is_weapon: bool = False
    is_enabled: bool = True
    import_custom_moveset: bool = True
    skill_moveset: Optional[SkillMovesetMetadata] = None

    @property
    def gender_restriction(self) -> Optional[str]:
        """Returns 'female' if set only has female parts, or None."""
        if self.is_weapon or not self.parts:
            return None
        genders = {p.gender_variant.lower() for p in self.parts if getattr(p, "gender_variant", None)}
        if genders == {"f"}:
            return "female"
        return None


@dataclass
class ManifestRecord:
    """
    Persisted record of an injected mod in lootforge_manifest.json.
    
    Why:
        Guarantees 100% auditability and allows clean 1-click uninstallation
        or re-rolling without leaving ghost entries or touching vanilla data.
    """
    set_id: str
    created_timestamp: str
    allocated_model_id: str
    allocated_param_id: int
    source_mod_name: str
    target_vanilla_name: str
    loot_route: str
    loot_target_name: str
    staged_files: List[str] = field(default_factory=list)
    custom_skill_name: Optional[str] = None
    custom_skill_id: Optional[int] = None
    has_custom_moveset: bool = False


@dataclass
class BackupRecord:
    """
    Metadata for an archived regulation.bin snapshot.
    """
    backup_file_name: str
    created_timestamp: str
    file_size_bytes: int
    sha256_checksum: str
