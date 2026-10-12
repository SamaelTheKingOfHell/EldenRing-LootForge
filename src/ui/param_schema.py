"""
Parameter schema and metadata descriptors for LootForge.

Defines input parameter types, categories/purposes, defaults, and bounds
for the mod generator and distribution engine.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Union
from src.models import AdditionType, AntiDup


class ParamType(Enum):
    """Supported parameter primitive and presentation types."""
    BOOL = auto()
    INT = auto()
    FLOAT = auto()
    ENUM = auto()
    STRING = auto()
    PATH_FILE = auto()
    PATH_DIR = auto()


class ParamPurpose(Enum):
    """
    Functional purpose and grouping for parameters.
    Governs placement and card container organization in the UI.
    """
    DROP_STYLE = "Loot & Drop Rules"
    DIABLO_ARPG = "Diablo ARPG Procedural Relics"
    PATHS = "Active Regulation & Paths"
    GENERAL = "Display & Mystery Settings"


@dataclass
class ParamDescriptor:
    """
    Metadata describing an engine/generator parameter.
    
    Why:
        Decouples parameter definition from UI layout and widget rendering.
        Enables data-driven auto-generation of settings panels per [CS-DECOUPLE].
    """
    key: str
    label: str
    param_type: ParamType
    purpose: ParamPurpose
    description: str = ""
    default: Any = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    unit: Optional[str] = None
    enum_class: Optional[type] = None
    enum_options: Optional[List[Tuple[str, Any]]] = None
    file_filter: Optional[str] = None


def get_generator_param_descriptors() -> List[ParamDescriptor]:
    """
    Returns the comprehensive list of input parameters for the generator,
    categorized by purpose and typed for automatic UI generation.
    """
    return [
        # --- Group 1: Drop Style & Rules (Enums, Multipliers) ---
        ParamDescriptor(
            key="addition_type",
            label="Addition Type",
            param_type=ParamType.ENUM,
            purpose=ParamPurpose.DROP_STYLE,
            description="Controls how standalone gear is mapped into game loot tables (Remembrances, enemies, or test).",
            default=AdditionType.STANDARD_ADDITION.value,
            enum_class=AdditionType,
            enum_options=[
                ("[1] Random Addition (Mobs / Non-dropped to Bosses & Shops)", AdditionType.RANDOM_ADDITION),
                ("[2] Standard Addition (Thematic Expected Drop / Shop)", AdditionType.STANDARD_ADDITION),
                ("[3] Test Mode (Distribute Across All Loot Pools for Verification)", AdditionType.TEST_MODE),
            ]
        ),
        ParamDescriptor(
            key="anti_dup",
            label="Anti-Dup Rule (100% Drops)",
            param_type=ParamType.ENUM,
            purpose=ParamPurpose.DROP_STYLE,
            description="Prevents duplicate drops for guaranteed and 100% loot items.",
            default=AntiDup.BOSS_ROTATION.value,
            enum_class=AntiDup,
            enum_options=[
                ("[1] Boss Rotation (Remembrances -> Elites -> Wild)", AntiDup.BOSS_ROTATION),
                ("[2] Everything in the Wild at Normal Rates", AntiDup.EVERYTHING_IN_THE_WILD),
            ]
        ),
        ParamDescriptor(
            key="global_multiplier_percent",
            label="Global Drop Multiplier",
            param_type=ParamType.FLOAT,
            purpose=ParamPurpose.DROP_STYLE,
            description="Global scaling multiplier applied to all enemy mob drop rates (100% = 1.0x baseline).",
            default=100.0,
            min_value=10.0,
            max_value=300.0,
            step=5.0,
            unit="%"
        ),

        # --- Group 2: Diablo ARPG Procedural Generator ---
        ParamDescriptor(
            key="diablo_loot_enabled",
            label="Enable Diablo Procedural Loot",
            param_type=ParamType.BOOL,
            purpose=ParamPurpose.DIABLO_ARPG,
            description="Transforms mod items into multi-tier ARPG relics with randomized rarities (Common-Mythic), prefixes, suffixes, and SpEffect passives.",
            default=False
        ),
        ParamDescriptor(
            key="diablo_variants_per_item",
            label="Variants Per Item Set",
            param_type=ParamType.INT,
            purpose=ParamPurpose.DIABLO_ARPG,
            description="Number of uniquely-rolled procedural ARPG variants generated for each mod item set (1 to 1,000 instances).",
            default=3,
            min_value=1,
            max_value=1000,
            step=1,
            unit="variants"
        ),
        ParamDescriptor(
            key="diablo_seed",
            label="RNG Deterministic Seed (Optional)",
            param_type=ParamType.INT,
            purpose=ParamPurpose.DIABLO_ARPG,
            description="Seed integer for deterministic reproducible affix rolls. Leave at 0 for dynamic random rolls.",
            default=0,
            min_value=0,
            max_value=2147483647,
            step=1
        ),
        ParamDescriptor(
            key="diablo_inject_vanilla_stats",
            label="Inject Stats into Vanilla Item Loots",
            param_type=ParamType.BOOL,
            purpose=ParamPurpose.DIABLO_ARPG,
            description="Directly infuses Diablo stats, element scalings, SpEffect passives, and affix lore into vanilla base weapons and armors.",
            default=False
        ),
        ParamDescriptor(
            key="diablo_use_vanilla_base_items",
            label="Use Vanilla Items as Base Items for Distribution",
            param_type=ParamType.BOOL,
            purpose=ParamPurpose.DIABLO_ARPG,
            description="Uses vanilla weapons and armor sets as base items to generate standalone procedural relics and distribute them across bosses, merchants, chests, and enemy drops.",
            default=False
        ),
        ParamDescriptor(
            key="diablo_randomize_weapon_skills",
            label="Randomize Weapon Skills (Ashes of War)",
            param_type=ParamType.BOOL,
            purpose=ParamPurpose.DIABLO_ARPG,
            description="Randomly rolls authentic Ashes of War and unique boss weapon skills (SwordArtsParam) on Diablo weapon variants.",
            default=False
        ),

        # --- Group 3: Paths & Installation ---
        ParamDescriptor(
            key="active_regulation_path",
            label="Active regulation.bin",
            param_type=ParamType.PATH_FILE,
            purpose=ParamPurpose.PATHS,
            description="Path to your currently active regulation.bin file (Mod Engine 2 mod/ folder or game profile).",
            default="",
            file_filter="Regulation Files (*.bin);;All Files (*)"
        ),
        ParamDescriptor(
            key="input_directory",
            label="Mod Input Folder",
            param_type=ParamType.PATH_DIR,
            purpose=ParamPurpose.PATHS,
            description="Folder containing raw downloaded replacer mod folders or archives.",
            default="input_mods"
        ),
        ParamDescriptor(
            key="output_directory",
            label="Mod Output Staging Folder",
            param_type=ParamType.PATH_DIR,
            purpose=ParamPurpose.PATHS,
            description="Folder where Mod Engine 2 loads staged standalone assets (typically 'mod').",
            default="mod"
        ),
        ParamDescriptor(
            key="game_directory",
            label="Game Installation Folder",
            param_type=ParamType.PATH_DIR,
            purpose=ParamPurpose.PATHS,
            description="Root directory containing eldenring.exe (for reading vanilla data and assets).",
            default=""
        ),

        # --- Group 4: General & Mystery Settings ---
        ParamDescriptor(
            key="global_spoiled",
            label="Mystery Mode (Hide Drop Locations)",
            param_type=ParamType.BOOL,
            purpose=ParamPurpose.GENERAL,
            description="Obfuscate enemy drop locations in the loot table behind mystery tags.",
            default=True
        ),
        ParamDescriptor(
            key="items_per_page",
            label="Modal Table Page Size",
            param_type=ParamType.INT,
            purpose=ParamPurpose.GENERAL,
            description="Number of items rendered per page in the loot inspection modal.",
            default=8,
            min_value=8,
            max_value=100,
            step=1
        ),
    ]
