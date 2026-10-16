"""Bounded, progression-locked placement shared by generation and capacity planning."""
import hashlib


class DestinationCapacityError(ValueError):
    """The requested region has no remaining independent reward slots."""


def companion_count(generator, spec, index, special):
    """Rare single bonus, independent of affix RNG so capacity and generation agree."""
    if not special:
        return 0
    key = f"{getattr(generator, 'seed', 0)}:{spec.get('set_id')}:{index}"
    return int(int.from_bytes(hashlib.blake2b(key.encode(), digest_size=4).digest(), 'little') % 100 < 7)


def choose_destination(generator, pools, spec, index, tier):
    """Reserve actual row capacity; never spill into a different table or unrelated pickup."""
    _, _, _, bosses, chests, merchants, enemies, _, _ = pools
    candidates = {'boss': bosses, 'chest': chests, 'merchant': merchants, 'enemy': enemies}
    usage = generator.__dict__.setdefault('_route_usage', {})
    cursors = generator.__dict__.setdefault('_route_cursors', {})
    count = len(spec.get('equip_params', []))
    order = ('boss', 'chest', 'merchant', 'enemy')
    start = index % len(order)
    for kind in order[start:] + order[:start]:
        records = candidates[kind]
        cursor_key = (kind, getattr(tier, 'value', tier))
        cursor = cursors.get(cursor_key, 0)
        for offset in range(len(records)):
            record = records[(cursor + offset) % len(records)]
            target = record.get('lotParamId') or record.get('id')
            is_shop = kind == 'merchant' or (kind == 'boss' and not record.get('lotParamId'))
            special = kind in ('boss', 'chest') and not is_shop
            table = 'map' if kind == 'chest' or (kind == 'boss' and record.get('isMapTable', True)) else 'enemy'
            # Boss/chest aliases and different rows in one award chain share a budget.
            key = ('shop', target) if is_shop else (table, int(target) // 10)
            used = usage.get(key, 0)
            limit = record.get('freeRows', float('inf'))
            if special:
                limit = min(limit, max(0, 4 - record.get('originalRewards', 1)))
            if used + count > limit:
                continue
            extra = companion_count(generator, spec, index, special and bool(pools[8]))
            # A bonus must never displace a piece of equipment or become a fifth reward.
            extra = min(extra, max(0, int(limit - used - count))) if extra else 0
            required = count + extra
            if is_shop and generator.is_shop_capacity_exceeded(record['id'], is_enia=(kind == 'boss')):
                continue
            usage[key] = used + required
            if is_shop:
                for _ in range(required):
                    generator.record_shop_allocation(record['id'], is_enia=(kind == 'boss'))
            cursors[cursor_key] = (cursor + offset + 1) % len(records)
            if kind == 'merchant':
                loot = {'type': 'merchant_shop', 'target_id': record['id'], 'shop_id': record['id'],
                        'range_start': record.get('rangeStart'), 'range_end': record.get('rangeEnd'),
                        'display_name': record['name'], 'cost_or_remembrance': record.get('defaultRuneCost', 8000)}
            elif kind == 'boss' and not record.get('lotParamId'):
                # Compatibility for explicitly curated Enia exchanges.
                loot = {'type': 'shop_lineup', 'target_id': record['id'], 'shop_type': 'finger_reader_enia',
                        'display_name': record['name'], 'cost_or_remembrance': record.get('defaultCost', 30000)}
            else:
                is_map = kind == 'chest' or (kind == 'boss' and record.get('isMapTable', True))
                loot = {'type': 'map_pickup' if is_map else 'enemy_drop', 'target_id': str(record['lotParamId']),
                        'lot_id': record['lotParamId'], 'display_name': record['name'],
                        'drop_rate_percent': 100.0 if is_map else record.get('defaultDropChance', 12.0)}
            loot['source_kind'] = kind
            return loot, kind == 'boss', record.get('boss', record['name']) if kind == 'boss' else None, record, kind == 'chest', extra
    # In data-only unit contexts an explicit caller route remains authoritative.
    if not any(candidates.values()):
        import copy
        loot = copy.deepcopy(spec.get('loot_distribution'))
        chest = bool(loot and loot.get('type') in ('map_pickup','map_drop','world_chest','chest_drop'))
        boss = bool(loot and loot.get('type') == 'boss_remembrance')
        extra = 0
        if chest or boss:
            target = loot.get('lot_id', loot.get('target_id'))
            key = ('map', int(target) // 10) if str(target).isdigit() else ('explicit', str(target))
            used = usage.get(key, 0)
            limit = max(0, 4 - loot.get('original_rewards', 1))
            if used + count > limit:
                raise DestinationCapacityError('The explicit boss/chest reward exceeds four total items.')
            extra = min(companion_count(generator,spec,index,bool(pools[8])), limit-used-count)
            usage[key] = used + count + extra
        return loot, boss, None, None, chest, extra
    raise DestinationCapacityError(f"No {getattr(tier, 'name', tier)} destination has room for {spec.get('set_id')}. Reduce variants or select fewer sets.")
