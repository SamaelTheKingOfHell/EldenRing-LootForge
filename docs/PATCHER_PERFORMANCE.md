# Patcher performance and correctness acceptance

Observed on 2026-10-14, Windows, Python 3.14 and .NET SDK 10.0.401 targeting net9.0.

## Measured improvement

| Controlled workload | Before | After |
| --- | ---: | ---: |
| Real backed-up regulation, 4,000 accessory injections and vanilla infusion, no enrichment or FMG input | 7.838 s | 3.155 s |
| 250 weapon variants with a synthetic 1,000-row imported behavior payload | 1.3707 s | 0.0137 s |
| Serialized variant batch for that payload | 35,637,701 bytes | 303,362 bytes |

The native measurement includes process startup, decryption, modification, serialization, encryption and output. Both resulting regulations were reopened through RegTool verification. It is not a timing claim for all 469 installed sets or an in-game benchmark. The generation test measures real generator code with controlled data, comparing the pre-change `83d6fa0` builder to the new builder.

Reproduce with `python tests/benchmark_patcher.py --before-dir scratch/regtool-before`. The before directory must contain the preserved runnable pre-change build. Results and logs are under `scratch/performance/`.

## Implemented changes

- Imported skills/behaviors/attacks appear once per set, then once per unique row across the whole serialized batch. Conflicting imported definitions produce an explicit error.
- Variant IDs come from one per-forge allocator; four-piece armor and neighboring sets no longer collide. Procedural rows use a separate namespace beginning at 100,000,000. Param-only vanilla bases use 200,000,000 and do not consume replacement model slots.
- Schema field indices, loot layouts, imported row IDs, world/tier pools and free loot-slot cursors are reused. Chest selection avoids repeated allocation and filtering of thousands of world candidates. Exhausted boss shops short-circuit immediately.
- Vanilla infusion shares the loaded regulation and message archive pass. It honors the skill-randomization setting, preserves fractional scaling, skips generated relics and tags infused vanilla rows to prevent repeated stat compounding. Existing previously compounded files still require a pristine backup to recover their original stats.
- Purging effects and skill tables reads row metadata first, avoiding full cell loading and rewriting when those tables have no generated rows.
- Boss/chest enrichment receives category-filtered equipment IDs. Existing chained vanilla rewards and tutorial slot-one rewards are preserved; new generated chains are tagged for later cleanup.
- Source rows with stripped names remain valid weapon/armor clone sources when their real attributes are valid.
- The regulation and messages are staged together. Failed message processing does not publish a partial regulation. Commit failures restore any already replaced outputs.
- Asset deployment targets the directory beside the selected regulation. Incremental copies replace newer unrelated files, detach existing hard links and keep downloads independent. Moveset assets are deployed once per input/target pair, with backups before replacement. Backups created within one second no longer overwrite each other.
- Missing regulation backups fail instead of creating placeholder game files. Batch staging failures propagate instead of being reported as successful.

## Dynamic maximum

`RegTool capacity` reads exact equipment row counts after excluding named LootForge rows that a forge purges. `variant_capacity.py` uses the same destination planning path as actual generation, including companion talismans, base chest companions and optional vanilla base distribution. Binary search finds the maximum within the supported 1..1,000 variant range.

The Qt control updates in a debounced background worker after source/settings/selection changes, lowers its maximum, and persists any clamped value. The forge repeats capacity calculation using its current source and knowledge snapshot. Native preflight independently rejects collisions and table overflow before cloning.

Before the additive-loot correction below, the observed 469-set selection and Ordo Perfectus source had these equipment-only limits:

| Mode | Maximum | Limiting table |
| --- | ---: | --- |
| Mod sets | 52 | EquipParamAccessory |
| Mod sets plus vanilla base items | 45 | EquipParamAccessory |

The actual Qt offscreen application was exercised through 52 → 45 → 52 by toggling vanilla inclusion, with persisted values and screenshots retained in `scratch/capacity-ui.json`, `scratch/capacity-mods.png` and `scratch/capacity-vanilla.png`. Existing vanilla rows are counted in both modes; in-place vanilla infusion does not create new equipment rows and therefore does not itself consume additional capacity.

## Verification and deployment

- Python suites: `python -m pytest tests -q` (see `scratch/pytest-final.log`).
- Native suites: `dotnet run --project tests/RegToolChecks -c Release -- .` (22 checks, see `scratch/native-checks.log`).
- Real-regulation benchmark roundtrips, Qt capacity transitions and Release compilation were exercised locally.
- The optimized executable is the Release RegTool loaded by `RegulationManager`; the desktop launcher reads the updated Python source on its next launch. Current local configuration was clamped to 52. No full reforge of the active game profile was performed as part of the benchmark or UI check.

## Remaining acceptance and audit findings

Release state: **Ship with Known Issues** for the local patcher; game-runtime acceptance needs another QA pass.

- Real Elden Ring runtime, save compatibility of the new procedural ID namespace, visible equipment, and observed acquisition/drop probabilities have not been exercised. Native roundtrips are separate evidence.
- Independent loot space is finite and now participates in the variant cap. Required placement failures abort publication; actual in-game acquisition and progression still require manual acceptance.
- Existing progression fallbacks can broaden to other candidate tiers when a tier pool is empty; C# enrichment also uses name/ID heuristics. Strict progression compliance needs a dedicated gameplay/distribution audit.
- Imported-regulation cache identity was corrected on 2026-10-15; the scoped conflict retest below passed. Independent gameplay acceptance remains open.
- Qt forging itself remains synchronous; the capacity worker is asynchronous. Large real forges can still make the main window unresponsive while working, although the engine work has been reduced.
- Native transaction staging covers regulation and FMGs. Asset staging/deployment and manifest writes are not one cross-file transaction; a disk/permission failure in those phases may require restoring the retained backup.

## Portable QA return

The required QA Tracker `qa_guide` and `qa_create` calls both returned that the independent tracker was unavailable. No QA ID, accepted retest or closed bug is claimed. Retain this report with the logs/artifacts listed above; import them into the tracker when available. The next manual owner should review the current source revision and run a copied-profile forge plus Elden Ring acquisition/save tests before accepting game-runtime behavior. Do not treat the implementation author's checks as that independent retest.

Publication boundary: `gh repo view` reports that the configured GitHub remote is public. Operations `agents/workflow.md` [WF-PRIVATE-REPO] requires explicit approval before using a public remote for local work. The change is committed and deployed locally; public push is held. After approval, the follow-up command is `git push origin HEAD:feature/souls-armor-port`.

## Imported attack ID 11 correction (2026-10-15)

The reported `Conflicting imported custom_attacks ID 11` was reproduced using the installed mod extractions. The Ab Aeterno and god_slaying_nagamaki rows differed only in `pad4`, a dummy8 field the native writer does not apply. The new comparison uses Paramdex writable field definitions, ignores extraction names and padding, and still rejects conflicting gameplay values for genuinely new row IDs with both set names and differing fields in the error.

Extraction also included unrelated weapons' attack catalogues. Python now imports only attack IDs referenced by the selected weapon's behavior variation. Native extraction uses `refType = 0` for attacks, keeping Bullet (`1`) and SpEffect (`2`) references separate; this mapping is confirmed by [Smithbox's Elden Ring BehaviorParam metadata](https://github.com/vawser/Smithbox/blob/main/src/Smithbox.Data/Assets/PARAM/ER/Param%20Meta/BehaviorParam.xml). Dependency tables are indexed once. An explicitly unmatched model no longer inherits the first weapon's moveset.

Import preflight reads host-owned row IDs and follows the existing native rule of preserving those rows. Previously generated `[LootForge]` rows are excluded because they are purged and must be reinstalled. No imported IDs are remapped. This preserves host/overhaul behavior; it does not establish compatibility for every mod skill or its external animation, Bullet and SpEffect dependencies.

Extraction cache version 2 includes the resolved source path, size, nanosecond modification time, native tool identity, relevant schemas and message archive identities. Legacy stem/size caches are bypassed, and changed sources invalidate in-memory entries too. The fallback importer now resolves tooling from the application root.

Retained implementation evidence:

- `scratch/import-fix-tests.log`: 145 Python tests passed in 47.77 seconds, including eight focused import/cache regressions.
- `scratch/import-fix-native.log`: 25 native checks passed, including an actual encrypted regulation extraction fixture distinguishing attack, Bullet and SpEffect references.
- `scratch/import-fix-reproduction.json` and `scratch/import-fix-specs.json`: all 469 current sets validated against the actual Ordo Perfectus source, using two variants per set (938 specs). Host-aware compaction retained 29 new skills, 216 behaviors and 193 attacks.
- `scratch/import-fix-roundtrip/patch-with-messages.log`: the native copied-output patch succeeded in 12.884 seconds, including base/DLC item text. It injected 2,864 equipment and text entries and 971 loot/shop entries. The output reopened successfully with 194 parameter files. This is a controlled two-variant regression, not the full configured 52-variant forge or an in-game test.
- The active game profile was not rewritten. The local Release patcher and Python source are the deployment target; a running desktop app must be restarted to reload them.

The independent QA Tracker was unavailable again when creating the reported bug record. This remains an unsubmitted portable return, without a QA ID or accepted retest. Next manual acceptance: restart the local app, rescan the same selection, forge a copied profile at the chosen capacity, then verify custom skills, acquisition and save/reload in Elden Ring. Record the deployed commit and target with the retained evidence before accepting runtime behavior.

## Additive loot correction and accessory investigation (2026-10-15)

The original-slot preservation check was insufficient: adding an item to an empty slot changes a row's lottery denominator. It can replace the original reward at acquisition time even when slot one was never overwritten. `AdditiveLootService` now adds an independent chained row with its own item/no-drop weights. Direct drops, shop overflow and boss/chest enrichment share this path. It preserves existing cells, avoids connecting an unrelated row across a gap, and leaves a separation between ten-ID routing blocks. Required distribution fails before output publication if independent space is exhausted; optional enrichment reports only successful additions. The variant maximum also counts available independent loot rows.

Existing profiles need more than clearing generated item IDs: their old no-drop weights may have been overwritten. `LegacyLootRecovery` compares unaffected binder files against retained clean backups, then verifies every unrelated field of affected rows before restoring only the changed slots. A mismatch stops publication. The real selected profile had 5,682 mixed rows successfully recovered from `regulation.bin.bak_20261015_063416_330195400` in a separate copied output. Category-aware purge avoids deleting an unrelated item with the same numeric ID in another equipment table.

The user reports newly acquired accessories showing `?AccessoryName?` with invisible icons in the English inventory. A read-only selected-profile audit found 64,936 generated accessory rows, zero missing English name entries, zero nonpositive icon IDs and no accessory loot references to missing rows. The table contains an out-of-order sentinel ID (`999999999` before procedural IDs). Explicit PARAM rows are now sorted before writing; the actual game inventory symptom remains awaiting reproduction/retest. The other installed language had none of the generated accessory names, so publication now covers installed language directories and their base/DLC archives. Missing name categories abort publication rather than reporting a false injection count. Obsolete generated text is pruned using known removed equipment IDs, preserving original/other-mod entries and avoiding repeated recompression of stale large archives.

Evidence is retained in `scratch/loot-text-before.json`, `scratch/additive-roundtrip/`, `scratch/additive-capacity-roundtrip/`, `scratch/additive-native.log`, and `scratch/additive-python-final.log`. The Python suite passed 146 tests and the isolated committed-source native suite passed 46 checks. `ProfileAudit` compares every original loot cell against the verified clean backup and checks the copied accessories/text. Both copied-output runs preserved all 10,727 original map/enemy loot rows without a changed cell. The two-variant, 469-set copy completed in 23.24 seconds with 2,864 generated equipment entries; its 1,846 accessories had no missing English/installed Chinese names or invalid icon IDs.

With independent loot capacity included, the current maximum is **39 variants for the 469 mod sets, or 30 with vanilla bases included**. A controlled maximum-capacity copy generated 44,209 equipment entries (including 24,358 accessories) in 107.3 seconds. Native placement succeeded for all 44,209; the output reopened with sorted accessory rows, zero invalid accessory icon IDs, zero missing accessory names in each installed base/DLC message table, and zero changed original loot rows. This uses a deterministic generation fixture with custom art disabled and separately imported dependencies; it is not an in-game or complete UI/asset-deployment test. See `scratch/additive-capacity-roundtrip/capacity.json`, `patch.log`, and `audit.json`.

The user narrowed the affected pickup to the first starting area. The independent QA Tracker remains unavailable; no bug ID, accepted retest or verified game-runtime closure is claimed. The next manual owner should fully exit Elden Ring before replacing outputs, launch the same ME3 profile, acquire a new accessory in that starting area, inspect its inventory name/icon, and compare original reward/drop behavior. The valid English output does not establish the root cause of the reported inventory symptom; the row-order and message-publication changes still require that runtime retest.

Concurrent Diablo-power edits appeared in the shared checkout during this work. Keep this change's commit and native release build scoped; uncommitted work from the other task is not evidence for this fix or part of its publication. The configured remote remains public and push remains held under the previously recorded publication boundary.

Local deployment: the isolated native build of `79db79f` was installed at the Release path used by `RegulationManager`, with matching file hashes and the previous runtime retained under `scratch/additive-runtime-before/`. Current configuration was lowered from 52 to 39 without replacing other settings. The selected active profile was not rewritten. Deployment identity, checks, profile hash and copied-output results are recorded in `scratch/additive-deployment.json`. Restart LootForge to load the changed Python code, fully exit Elden Ring, and reforge before the starting-area acquisition retest.

## Immediate vanilla-toggle clamp (2026-10-15)

Fresh-launch reproduction showed that the previous controller eventually clamped the value after another background calculation. The worker now calculates both vanilla modes from the same source counts and selection. Once ready, a vanilla-only toggle synchronously applies the matching maximum, lowers the displayed/configured count if necessary and saves it before the checkbox signal returns. Disabling vanilla raises the available maximum without raising the user's chosen count. Source or native tool changes invalidate the pair; selection/path changes still trigger background calculation. Outdated worker successes and failures cannot restore an old limit.

`scratch/vanilla-toggle-tests.log` records 20 focused Qt/capacity checks passing. An actual offscreen Qt window scanned the 469 installed sets, read the selected real regulation through the deployed native tool, and toggled the real checkbox using a temporary configuration: 25/25 → 21/21 → 25/21 (maximum/value), with persisted values verified. Enabling vanilla took 4.063 milliseconds and disabling it took 3.260 milliseconds, including synchronous configuration saves. These current limits include concurrent, uncommitted generator changes and supersede neither the earlier isolated-build measurements nor their scope. See `scratch/vanilla-toggle-verified.json` and `.log`; this is Qt signal/state evidence, not physical user testing or game-runtime acceptance. No active configuration or regulation was changed by this check.

This Python-only fix is installed in the source loaded by the desktop launcher; restart LootForge to load it. The QA Tracker guide/create calls remained unavailable, so this is an unsubmitted portable QA return with no tracker ID or independently accepted retest. Public push remains held at the publication boundary above.
