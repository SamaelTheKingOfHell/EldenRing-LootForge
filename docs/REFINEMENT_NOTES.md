# Equipment balance refinement

The in-game reports reopen acceptance of the preceding runtime repair. Work is
tracked in [the refinement checklist](REFINEMENT_CHECKLIST.md); exact deployed
identities and measured results are in `REFINEMENT_VALIDATION.json`.

## Armor

Elden Ring's ordinary armor uses zero in its obsolete flat defense fields and
separate native damage-cut rates for negation. The schema defaults those flat
fields to 100, and previous affixes also added flat defense. The selected-profile
audit found inflated flat defense, although the exact all-100 combination was
not reproduced in that file snapshot. A real-schema regression explicitly covers
all-100 defaults.

Generated armor now keeps all eight flat defense fields at zero. Affix defense
points add tenths of a percentage point to the corresponding native negation,
limited to three percentage points per affix. Final per-piece negation and poise
are bounded by slot and region. Early head/body/arms/legs caps are 6/16/5/9.5%;
endgame caps are 7.5/22/6.5/12.5%. Weaker native protection remains weaker rather
than being raised automatically to the cap. Host armor base stats are preserved.

## Weapons and useful effects

The universal 120-damage starter ceiling is removed. Bonus limits are relative
to the cloned native weapon and preserve every original damage channel, scaling
and requirement. Elemental bonuses cannot consume the weapon's original physical
damage budget. Region scaling can be disabled without turning additive affixes
into replacement base stats.

Added on-hit status effects use free behavior slots and preserve inherited
buildup and its UI entry. Rolled passive scales have a 0.5 minimum, positive
buildup stays meaningful, and active integer effects cannot round to zero.
Extra resource passives have a 2% minimum, warding a 1% minimum and regeneration
at least one point. Explicitly setting the stat multiplier to zero still disables
the added bonuses. Passive message slots are captured/restored along with native
effect slots; the deployed history was migrated from the retained pre-refinement
PARAM/state to cover missing UI originals from the older format.

The native Uchigatana regression starts with 115 physical attack and 45 bleed.
An early legendary retains at least that physical damage and original bleed,
adds bounded damage, and adds at least 22 buildup in the controlled half-strength
status roll. This is a data check, not an enemy damage or proc-rate game test.

## Vanilla preservation and economy

Vanilla infusion emits no names, captions or info and no price overrides. Native
patching also rejects text replacement for original item IDs. Per-language,
per-archive history restores prior LootForge text and prices while preserving
intervening external changes. The retained history contains clean original
descriptions; no clean-reference fallback was needed. Legacy sweep commands
preserve vanilla text too.

Finalized PARAM damage, scaling, damage negation, poise, status, passive strength
and combat enchantments determine generated equipment prices. Tier, rarity labels
and boss prestige have no independent premium. The Python UI provides conservative
previews; native final prices and vendor stock use actual resulting fields.
Purchases are bounded to 300–12,000 runes. Sale returns are approximately 5%,
bounded to 10–500 runes. Vanilla item prices remain original.

## Independent aura controls

`diablo_weapon_auras_enabled` controls weapons and shields;
`diablo_armor_auras_enabled` controls armor. Both default off. An old
`diablo_auras_enabled` setting migrates to both unless an explicit category value
is present. New saved configurations contain the two category booleans. The
legacy constructor argument remains compatible. Actual Qt controls and
category-independent output are tested; changing auras does not reroll combat stats.

## Acceptance boundary

The profile is reforged through the normal backup/asset/manifest pipeline. Final
checks cover complete routes, every generated armor/price, original loot and
common events, every tracked vanilla text and original price field. Saves are
untouched. Restart the game before retesting; verify visible stats, actual damage
and buildup, purchases/sales, original lore and aura/buff behavior in game.
The QA tracker was unavailable; the portable assignment remains awaiting game retest.

Native field evidence: vendored Paramdex definitions and the primary
[EquipParamProtector schema](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/EquipParamProtector.xml),
[SpEffect schema](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/SpEffect.xml),
plus read-only comparisons with the installed retail and selected-profile PARAMs.
