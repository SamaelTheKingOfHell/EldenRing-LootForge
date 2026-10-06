"""
ID allocator and namespace collision guard for LootForge.

Allocates unique standalone IDs for model parts and regulation parameters in safe ranges,
preventing conflicts with base game items and official DLC additions.
"""

from typing import Set, Dict, Optional
from src.models import StandaloneAllocation
from src.logger import system_logger


class IdAllocator:
    """
    Manages safe ID ranges for standalone mod integration.
    
    Why:
        Guarantees that newly generated armor and weapon parts do not collide
        with vanilla game data, Shadow of the Erdtree expansion IDs, or previously
        installed custom mods.
        
    Example:
    ```python
    allocator = IdAllocator(min_model_id=9000, max_model_id=9999)
    alloc = allocator.allocate("custom_set_1")
    print(alloc.new_model_id)  # "9000"
    print(alloc.new_equip_param_id)  # 9000000
    ```
    """

    def __init__(
        self,
        min_model_id: int = 9000,
        max_model_id: int = 9999,
        base_param_id: int = 9000000,
        base_item_lot_id: int = 9100000
    ):
        self._min_model_id = min_model_id
        self._max_model_id = max_model_id
        self._base_param_id = base_param_id
        self._base_item_lot_id = base_item_lot_id

        self._allocated_models: Set[int] = set()
        self._set_to_allocation: Dict[str, StandaloneAllocation] = {}

    def register_used_model_id(self, model_id: int) -> None:
        """Marks a model ID as in-use."""
        self._allocated_models.add(model_id)

    def allocate(self, set_id: str) -> StandaloneAllocation:
        """
        Allocates the next available standalone model and param IDs for a mod set.
        """
        if set_id in self._set_to_allocation:
            return self._set_to_allocation[set_id]

        candidate = self._min_model_id
        while candidate in self._allocated_models and candidate <= self._max_model_id:
            candidate += 1

        if candidate > self._max_model_id:
            raise RuntimeError(f"Exhausted available standalone model IDs ({self._min_model_id}-{self._max_model_id}).")

        self._allocated_models.add(candidate)
        offset = candidate - self._min_model_id

        allocation = StandaloneAllocation(
            new_model_id=str(candidate),
            new_equip_param_id=self._base_param_id + (offset * 1000),
            new_item_lot_id=self._base_item_lot_id + offset,
            marker_tag="✦ [LootForge]"
        )

        self._set_to_allocation[set_id] = allocation
        system_logger.info(
            f"Allocated IDs for set '{set_id}': Model={allocation.new_model_id}, "
            f"Param={allocation.new_equip_param_id}, Lot={allocation.new_item_lot_id}",
            source="IdAllocator"
        )
        return allocation

    def release(self, set_id: str) -> None:
        """Releases an allocation for a given set."""
        if set_id in self._set_to_allocation:
            alloc = self._set_to_allocation.pop(set_id)
            model_int = int(alloc.new_model_id)
            self._allocated_models.discard(model_int)
            system_logger.debug(f"Released model ID {model_int} for set '{set_id}'", source="IdAllocator")

    def reset(self) -> None:
        """Clears all dynamic allocations."""
        self._allocated_models.clear()
        self._set_to_allocation.clear()
