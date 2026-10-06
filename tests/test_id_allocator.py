"""
ID allocator test suite.

Validates that model IDs and param IDs are allocated within safe ranges without collision.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.id_allocator import IdAllocator


class TestIdAllocator(unittest.TestCase):
    """
    Validates namespace safety and collision prevention.
    """

    def setUp(self):
        self.allocator = IdAllocator(min_model_id=9000, max_model_id=9005)

    def test_sequential_allocation(self):
        """Verifies sequential standalone ID allocation."""
        alloc1 = self.allocator.allocate("set_a")
        self.assertEqual(alloc1.new_model_id, "9000")
        self.assertEqual(alloc1.new_equip_param_id, 9000000)

        alloc2 = self.allocator.allocate("set_b")
        self.assertEqual(alloc2.new_model_id, "9001")
        self.assertEqual(alloc2.new_equip_param_id, 9001000)

    def test_idempotent_allocation(self):
        """Ensures requesting the same set_id returns the identical allocation."""
        alloc1 = self.allocator.allocate("set_a")
        alloc2 = self.allocator.allocate("set_a")
        self.assertEqual(alloc1.new_model_id, alloc2.new_model_id)
        self.assertEqual(alloc1.new_equip_param_id, alloc2.new_equip_param_id)

    def test_exhaustion_protection(self):
        """Verifies exception when safe ID range is exhausted."""
        for i in range(6):  # 9000 through 9005
            self.allocator.allocate(f"set_{i}")

        with self.assertRaises(RuntimeError):
            self.allocator.allocate("set_overflow")


if __name__ == "__main__":
    unittest.main()
