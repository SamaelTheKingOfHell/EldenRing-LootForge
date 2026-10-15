# Diablo power, combat magic and auras

These controls belong to the desktop Diablo panel. The Diablo master switch must
be enabled for this generator to run. Restart LootForge after updating its source
and reforge to apply changed settings to game files.

## Controls

| Setting | Default | Behavior |
| --- | --- | --- |
| Progression-scaled Diablo power | On | Region and rarity scale bonus stats, affix values and cloned passive potency. |
| Additional Diablo passives | Off | Magic occasionally gains one extra passive; Rare gains one, Legendary two, Mythic three. |
| Rare legendary combat magic | Off | Legendary items have a 6% enchantment chance; Mythic items have 14%. Lower rarities cannot roll one. |
| Optional Diablo item auras | Off | Persistent cosmetic visuals matching rolled elemental, status, magic or healing effects. |

Early/Mid/Late/Endgame potency factors are `0.40/0.75/1.15/1.65`.
Common/Magic/Rare/Legendary/Mythic factors are `0.50/0.70/0.90/1.15/1.40`.
Ordinary affix values vary by another 90–110%; native passive/proc strength uses
bounded quarter-step buckets to share effect rows across many items. Base attack
and flat defense receive an additional `10% * regional rarity potency` bonus.
Affix stat changes add to the original equipment values.

Early ordinary drops use weights `40/43/15/1.8/0.2`, retaining rare early
Legendary/Mythic discoveries. Mid: `25/40/28/6/1`; Late: `15/35/35/12/3`;
Endgame: `10/30/40/16/4`.
Boss weights by region are `0/10/75/13/2`, `0/5/60/30/5`, `0/0/35/55/10`,
and `0/0/15/65/20`; chest weights are `15/43/35/6.5/0.5`, `10/30/45/13/2`,
`5/20/45/25/5`, and `0/10/40/40/10`. Early high-rarity discoveries remain
possible on every route without making every chest Legendary. Turning regional
power off retains the legacy boss/chest Legendary/Mythic guarantee.
Affix rarity floors now apply at every rarity. Region pools stay within their
tier when progression scaling is enabled.

## Enchantments

| Equipment | Trigger | Effect | Cooldown |
| --- | --- | --- | --- |
| Weapon | Attacking, using the game's swing-window signal | Glintstone projectile | 6 seconds |
| Shield, including Buckler | Guarding | Glintstone projectile or HP recovery | 10 seconds |
| Armor | Incoming damage removes an armed damage sentinel | Outward magic retaliation burst or HP recovery | 8 / 12 seconds |

Retaliation fires six projectiles around the wearer. It does not identify the
attacker or return a percentage of the incoming hit. Healing and spell damage
scale with rolled potency. These are automatic additional effects; they do not
replace the manual Ash of War. The separate weapon-skill randomization setting
continues to control that skill.

Combat magic merges events into the selected profile's `event/common.emevd.dcx`,
or uses the unpacked game's common script as the initial source. Other events
remain intact. Owned events contain a signature, and conflicting reserved IDs
fail before publication. Initializers precede existing constructor control flow.
No HKS, animation or executable patch is required by this implementation.

## Cosmetic auras

Nine themes follow actual rolled effects: fire, lightning, glintstone, holy,
frost, blood, poison, scarlet rot and renewal. Elemental blades use native
weapon enchantment visuals; clothing uses native body glows, frost wisps,
status particles or regeneration light. A physical item without a matching
magical effect stays plain. Turning auras on consumes no random rolls and
changes no item stats, affixes, passive rolls or combat-magic odds.

The implementation copies only visual rows and attaches their VFX references.
It does not copy grease damage, status mechanics, weapon-enchant categories or
buff eligibility. Cosmetic priority is 255; lower-priority-number temporary
buff visuals can take precedence in the same category. Weapon left/right
attachment and return of the cosmetic effect after a temporary buff expires
remain explicit in-game checks. Shared source VFX and SpEffects stay intact.
Auras merge into a resident effect to preserve passive capacity; a conditional
resident can make that item's visual conditional too.

## Reforging and recovery

`lootforge_diablo_texts.json` also restores names and descriptions separately for
each language/archive when infusion is disabled.

`lootforge_diablo_fields.json` records original/applied vanilla fields in one
batched write. A later reforge restores the previous values before rerolling.
If another mod changed a tracked field, that new value becomes its base instead
of being overwritten by restoration. This prevents repeated infusions from
stacking bonuses and lets disabled options remove their old effects.

Weapon families share their roll while retaining each member's own base damage
and reinforcement configuration. Extra numeric passives can merge into an
unconditional resident effect when special equipment has no empty resident slot.
Shared vanilla SpEffects remain unchanged; scaled chains are cloned. Unknown
SpEffect bit padding is retained through serialization.

The regulation, messages, infusion state and generated common script publish in
the same transaction. The desktop forge backs up existing sidecars and tracks
new ones with its existing rollback ledger.

## Validation and limits

- Deterministic Python checks cover rarity floors, early Legendary probability,
  regional strength and boss/chest rarity, equipment categories, proc frequency, aura determinism, settings, one-variant
  generation, zero multipliers and strict region fallback.
- Native checks use installed game/profile PARAM templates and controlled generated
  items; they exercise reference integrity, serialization, undocumented bit
  retention, infusion restoration, external edits, all nine aura themes and common-script enable/disable.
  Native checks also assert instruction argument layouts and initializer counts to
  prevent the SoulsFormats layer/argument constructor ambiguity from recurring.
- The copied-profile pipeline processed 1,555 infusion specifications, covering
  3,508 weapon rows, 793 armor rows and 156 accessory rows, plus 4,664 item texts.
  These are local generated-data observations, not combat acceptance.
- Headless Qt checks and a rendered Diablo card verify control wiring and layout.
- Actual swing/guard signals, incoming-damage sentinel behavior, player-owned
  projectiles, healing, cooldowns, aura rendering/buff overlap and equip transitions still require in-game QA.

Primary implementation references: the vendored Paramdex ER definitions and names;
[ER EMEDF](https://soulsmods.github.io/emedf/er-emedf.html) for event instructions;
[Smithbox ER enums](https://github.com/vawser/Smithbox/tree/main/Smithbox.Release/Output/Assets/PARAM/ER/Param%20Enums)
for native state/parameter labels. The damage-deletion enum is incompletely named,
so successful serialization does not establish its runtime trigger behavior.

The QA tracker endpoint was unavailable during this change. The portable game QA
assignment is retained in `DIABLO_MAGIC_QA.json`; it is unsubmitted and unexecuted.

The retained run summary is `DIABLO_POWER_VALIDATION.json`. Generate reproducible
native coverage specs with `tests/DiabloChecks/build_specs.py`, then use the
command documented in that folder. The fixture seed is 94715; forced aura
coverage and elevated rarity fixtures do not represent ordinary loot odds.

Final local acceptance: 144 Python tests, 46 existing native regressions and
11,142 Diablo native checks passed across 2,355 real-template coverage items.
The copied-profile reroll retained identical hashes for regulation, common script
and both state files. Disabling restored 60,572 fields and 13,371 text entries,
with no generated Diablo effects, visuals, projectiles, behaviors, attacks or
events remaining. These counts do not establish in-game behavior.
