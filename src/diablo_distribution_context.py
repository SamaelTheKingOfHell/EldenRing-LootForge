"""Shared per-forge world/tier pools, reused by generation and capacity planning."""


def distribution_context(generator, kb, tier):
    """Partition immutable world candidates once per knowledge base and progression tier."""
    cache = getattr(generator, "_distribution_contexts", None)
    if cache is None:
        cache = generator._distribution_contexts = {}
    key = (id(kb), tier)
    if key in cache:
        return cache[key]
    pools = kb.get_diablo_distribution_pools() if (kb and hasattr(kb, "get_diablo_distribution_pools")) else None
    elites = []
    raw_bosses, raw_merchants, raw_chests = [], [], []
    boss_pool, chest_pool, merchant_pool, enemy_pool = [], [], [], []
    if pools:
        raw_bosses = pools.get("bosses", [])
        raw_merchants = pools.get("merchants", [])
        raw_chests = pools.get("chests", [])
        raw_elites = pools.get("elites", [])
        raw_roaming = pools.get("roaming", [])

        if tier and kb and hasattr(kb, "get_progression_tier"):
            boss_pool = [b for b in raw_bosses if kb.get_progression_tier(b) == tier] or ([] if generator.progression_scaling else raw_bosses)
            chest_pool = [c for c in raw_chests if kb.get_progression_tier(c) == tier] or ([] if generator.progression_scaling else raw_chests)
            merchant_pool = [m for m in raw_merchants if kb.get_progression_tier(m) == tier] or ([] if generator.progression_scaling else raw_merchants)
            elites = [e for e in raw_elites if kb.get_progression_tier(e) == tier] or ([] if generator.progression_scaling else raw_elites)
            roaming = [r for r in raw_roaming if kb.get_progression_tier(r) == tier] or ([] if generator.progression_scaling else raw_roaming)
        else:
            boss_pool, chest_pool, merchant_pool = raw_bosses, raw_chests, raw_merchants
            elites, roaming = raw_elites, raw_roaming
        enemy_pool = (elites + roaming) if (elites or roaming) else []

    acc_catalog = kb.list_all_discovered_accessories() if (kb and hasattr(kb,"list_all_discovered_accessories")) else {}
    if not acc_catalog and kb and hasattr(kb,"list_all_vanilla_accessories"):
        acc_catalog = kb.list_all_vanilla_accessories()
    if tier and generator.progression_scaling:
        acc_catalog = {key: info for key,info in acc_catalog.items() if info.get("progressionTier",1)==getattr(tier,"value",tier)}
    result = (pools, raw_bosses, raw_chests, boss_pool, chest_pool, merchant_pool, enemy_pool, elites, acc_catalog)
    cache[key] = result
    return result
