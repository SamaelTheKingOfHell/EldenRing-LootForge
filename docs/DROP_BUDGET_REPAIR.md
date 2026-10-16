# Boss and chest reward budget repair

The reported eight-to-ten item drops came from repeated variants reserving physical
row space without a shared four-item reward budget. The installed profile had 83
proven boss/chest destinations over budget, with a maximum of ten rewards.

Generation now reserves at most four total rewards per destination, including
original rewards. Every armor piece and bonus talisman consumes one slot.
Multiple sets, variants, boss/chest aliases and row aliases share the budget.
An optional talisman is omitted when the primary equipment fills the remaining
space. A complete armor group moves to another verified destination in its
progression tier when it cannot fit; equipment is not silently discarded.

The native patcher independently checks the aggregate chain before appending a
direct reward group. Boss and chest enrichment use the same remaining budget,
so they cannot each add another bundle. Invalid direct groups fail before any
member is appended and before output publication.

A lottery's alternative slots count as one possible reward, and a native
consumable stack counts as one reward entry. All generated equipment has quantity
one. Original rows, weights, quantities and acquisition flags remain unchanged.
Five existing boss bundles already contain five original rewards: Vyke,
Dancing Blade of Ranah, Greatsword of Solitude, Red Bear's Claw and Rakshasa's
Great Katana. They receive no additional loot. Removing original rewards would
violate the vanilla-preservation requirement.

The selected 469 input groups fit at two variants per item under the new limits;
the former three-variant selection exceeded regional destination capacity.
The normal forge pipeline applies and persists this capacity clamp.

Implementation and deployed-file evidence belongs in `DROP_BUDGET_VALIDATION.json`.
The portable retest in `DIABLO_MAGIC_QA.json` remains unexecuted in the actual game.
Restart LootForge and Elden Ring before testing fresh boss/chest rewards.
