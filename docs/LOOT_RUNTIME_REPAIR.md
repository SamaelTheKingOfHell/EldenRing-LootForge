# Loot routing and inventory repair, 2026-10-16

The subsequent [equipment refinement](REFINEMENT_NOTES.md) replaces this document's
starter damage ceiling, flat-defense handling, economy and combined aura control.
The routing and inventory identity repairs remain applicable.

The reported screenshots exposed independent identity, layout and placement faults.
This repair uses the installed regulation, MSBs, event scripts and talk scripts as
the source of destinations. File checks below do not establish game acceptance.

| Fault | Repair |
| --- | --- |
| Name, rarity and caption disagree | Allocate weapons in 100-ID blocks, reserving the low digits for reinforcement. Choose canonical base weapons rather than whichever affinity was discovered last. |
| Caption overlaps the native skill panel | Limit generated captions to six wrapped lines and remove the duplicate skill/economy section. |
| Unknown accessory in inventory | Use a separate, collision-checked accessory range, native accessory item/shop categories, sorted PARAM rows, cloned icons and base/DLC name, info and caption entries. The chosen range is conservative; it is not evidence of a universal 16-bit accessory limit. |
| Same medallions everywhere | Remove the unconditional two-accessory bundle. Only boss/chest groups have a deterministic 7% chance of one bonus from discovered, region-matched talismans. |
| Ingredients and starter pickups award gear | Require actual NPC equipment-drop references, actual chest records or boss award events. No arbitrary overflow into other rows or tables. |
| Chests refill after ordinary respawn | Added map rows inherit the original acquisition flag; corpse pickups and gathering nodes cannot qualify as chests. Boss awards remain gated by their original event. |
| Boss routing fails | Resolve actual AwardItemLot arguments through boss-defeat events and source remembrance rewards; route generated Diablo boss loot to that map reward. |
| Vendor additions invisible or repeated | Insert inside OpenRegularShop ranges extracted from ESD; preserve OpenTranspositionShop as an explicitly separate Enia exchange. Generated vendor stock is one item with its own stock flag. Full ranges fail. |
| Armor disappears from distribution | Reserve the complete equipment group before choosing a route; fail/clamp capacity rather than dropping pieces. Verify each armor slot has a deployed model asset and a reachable category-3 award or type-1 shop row. |
| Starter rolls overpower progression | Reduce regional power to 0.18/0.60/1.05/1.55, scale inherited resident passives including discovery and attributes, and cap imported base weapon power and early armor absorption. |

The world catalog distinguishes `MSBE.Treasure.InChest == 1` containers from
corpse/item glows (`2`). A qualifying chest must have an attached part, an existing
lot and a positive acquisition flag. Boss classification uses event provenance,
not a guaranteed-item weight. NPC pools require an MSB-to-NpcParam-to-equipment
lot reference. Shop intervals must be opened by installed talk scripts.

Progression classification uses named regions, dungeon map families and coarse
overworld coordinates. Overhaul-specific progression may need additional mappings;
the four tiers are not a traversal or player-level simulation.

On the selected profile, discovery found 95 boss roots, 214 one-time chest roots,
496 NPC gear-drop groups and 41 regular shop ranges, plus Enia's exchange range.
Not every root has free contiguous space. The planner fits three rolls per input
item for this 469-group selection, replacing the configured 25-roll request.
The deployed result has 1,203 weapons, 324 armor pieces and 32 bonus accessories
drawn from 30 distinct native talisman bases.
All 68 armor input groups have all three variants: 204 armor routes, including
54 vendor groups. Total vendor stock is 80 individual items across 68 placements.

The current selected regulation had changed independently since the preceding
forge, while old messages and Diablo sidecars remained. The repair backs up and
uses the currently selected source. It does not restore an older regulation or
edit saves. Previously held items with obsolete generated IDs require reacquisition;
this patch does not migrate their saved identities.

Validation is retained in `LOOT_RUNTIME_VALIDATION.json`. The exact-file verifier
checks source loot preservation, table ordering, all generated IDs, every complete
award, armor assets, vendor category/stock and installed base/DLC FMGs. Game QA is
still required for visible descriptions, boss/chest acquisition, normal rest/reload,
vendor purchases and armor visuals. Existing world-reset hotkeys remain unchanged.

Primary references:

- [SoulsRandomizers GameData](https://github.com/thefifthmatt/SoulsRandomizers/blob/master/RandomizerCommon/Core/GameData.cs): weapon base-ID normalization and distinct item-lot/shop category mappings.
- [Smithbox ER item-lot enum](https://github.com/vawser/Smithbox/blob/main/Smithbox.Release/Output/Assets/PARAM/ER/Param%20Enums/ITEMLOT_ITEMCATEGORY.json): armor category 3, accessory category 4.
- [ESDLang ER talk documentation](https://github.com/thefifthmatt/ESDLang/blob/master/dist/ESDScriptingDocumentation_Talk.json): OpenRegularShop 1[22] and OpenTranspositionShop 1[111].
- [ER EMEDF](https://soulsmods.github.io/emedf/er-emedf.html): initialization argument layouts, boss defeat and item-lot awards.
- Vendored SoulsFormatsNEXT `MSB/MSBE/EventParam.cs`: native treasure attachment and InChest fields.

Canonical research is also stored in THE ORDER's `knowledge/research/elden-ring-loot-forge`.
