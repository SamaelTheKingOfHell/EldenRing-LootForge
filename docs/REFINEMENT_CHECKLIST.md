# Loot refinement checklist

Branch: `codex/loot-refinement`. Reported game behavior reopens balance acceptance.

- [x] Armor: trace the all-100 values, correct native base/absorption fields and verify every generated piece against real reference equipment.
- [x] Weapon buildup: retain native status buildup and give added status affixes useful positive values; prevent rounded-to-zero effects.
- [x] Early legendary weapons: compare damage, scaling, requirements and buildup with a base Uchigatana and equivalent weapon classes; preserve progression without making relics worse than their base.
- [x] Vanilla descriptions: stop writing vanilla names/info/captions; restore earlier LootForge text using its per-language history and clean reference archives where required.
- [x] Economy: value actual finalized equipment strength, remove tier/rarity/prestige price premiums and lower sell returns to prevent rune inflation.
- [x] Aura controls: independent booleans for weapon auras and armor auras, including persisted settings, UI and legacy-config migration.
- [x] Regression coverage: real PARAM/FMG comparisons, positive native effects, category toggles, strength-only prices and fresh output checks.
- [x] Deployment: back up the current selected profile, stage/review, publish corrected regulation/messages/events, retain hashes, commit and push.
- [ ] Game retest: acquire fresh items, inspect armor, compare a starting legendary with Uchigatana, test buildup, vendor/sell values, original descriptions and each aura toggle separately.

QA tracker: unavailable during initial discovery. Retain a portable retest packet;
file verification does not close the reported game bugs.

Measured checks: 152 Python tests, 60 native regressions, 11,084 magic checks, 64,730 published routing checks and 105,667 published refinement checks passed.
Runtime acceptance remains awaiting game retest; the checked entries above describe implementation, deployment and file/controlled verification.
