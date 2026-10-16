"""Exact equipment capacity planning using the same destination planner as real variant generation."""

from collections import Counter
from dataclasses import dataclass

from src.diablo_generator import DiabloLootGenerator
from src.diablo_variant_builder import DiabloVariantBuilder
from src.diablo_vanilla_base_distributor import VanillaBaseDistributor
from src.id_allocator import IdAllocator


@dataclass(frozen=True)
class VariantCapacity:
    """Maximum accepted roll count and its exact projected equipment row totals."""
    maximum: int
    existing: dict
    generated: dict
    limiting_tables: tuple


def calculate_capacity(existing, mod_specs, knowledge_base, include_vanilla=False, ceiling=1000):
    """Find the largest roll count that fits every equipment table, including all companion talismans."""
    specs = list(mod_specs)
    if include_vanilla:
        specs.extend(VanillaBaseDistributor.generate_distribution_specs(knowledge_base, IdAllocator(), 0, None))

    contexts = {}

    def projected(variants):
        generator = DiabloLootGenerator(seed=0, knowledge_base=knowledge_base)
        generator._distribution_contexts = contexts
        totals = Counter()
        from src.diablo_destinations import DestinationCapacityError
        try:
            for spec in specs:
                totals.update(DiabloVariantBuilder.generate_variants(generator, spec, variants, knowledge_base, count_only=True))
        except DestinationCapacityError:
            return None
        return dict(totals)

    def fits(totals):
        return (totals is not None and all(existing.get(table, 0) + count <= 65535 for table, count in totals.items())
                and sum(totals.values()) <= existing.get("IndependentLootRows", float("inf")))

    # Primary equipment imposes a cheap upper bound before destination simulation.
    primary = Counter(ep["param_table"] for spec in specs for ep in spec.get("equip_params", []))
    upper = min([ceiling] + [max(0, (65535 - existing.get(table, 0)) // count) for table, count in primary.items() if count])
    low, high = 0, upper
    while low < high:
        middle = (low + high + 1) // 2
        if fits(projected(middle)):
            low = middle
        else:
            high = middle - 1
    totals = projected(low) if low else {}
    next_totals = projected(low + 1) if low < ceiling else totals
    limiting = tuple(table for table, count in (next_totals or {}).items() if existing.get(table, 0) + count > 65535)
    if next_totals is None:
        limiting += ("LootDestinations",)
    if next_totals is not None and sum(next_totals.values()) > existing.get("IndependentLootRows", float("inf")):
        limiting += ("IndependentLootRows",)
    return VariantCapacity(low, dict(existing), totals, limiting)


def clamp_variants(config, capacity):
    """Clamp persisted roll counts to the current selection's capacity; zero capacity blocks forging."""
    if capacity.maximum < 1:
        raise ValueError("The selected regulation has no room for this selection. Select fewer items.")
    previous = config.diablo_variants_per_item
    config.diablo_variants_per_item = max(1, min(int(previous), capacity.maximum))
    return previous != config.diablo_variants_per_item
