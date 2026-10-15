using System.Runtime.CompilerServices;
using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Amortized linear first-fit overflow allocation for monotonically filled loot tables.</summary>
public static class LootSlotAllocator
{
    private sealed class Cursor { public int Row; public int Slot = 1; }
    private static readonly ConditionalWeakTable<PARAM, Cursor> Cursors = new();

    /// <summary>Find the next empty slot 2..8 in table order, preserving slot 1 and full rows.</summary>
    public static (PARAM.Row Row, int Slot)? Next(PARAM param, ItemLotLayout layout)
    {
        var cursor = Cursors.GetOrCreateValue(param);
        while (cursor.Row < param.Rows.Count)
        {
            var row = param.Rows[cursor.Row];
            if (ParamHelper.GetCellIntFast(row, layout.ItemIdIndices[0]) > 0)
            {
                while (cursor.Slot < 8)
                {
                    int slot = cursor.Slot++;
                    if (ParamHelper.GetCellIntFast(row, layout.ItemIdIndices[slot]) == 0)
                        return (row, slot);
                }
            }
            cursor.Row++;
            cursor.Slot = 1;
        }
        return null;
    }
}
