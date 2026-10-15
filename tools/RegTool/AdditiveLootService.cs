using System.Runtime.CompilerServices;
using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Add independent loot rolls without changing an existing reward or its probability.</summary>
public static class AdditiveLootService
{
    private static bool IsOriginalRoot(PARAM.Row row) => row.ID > 0 && row.Name?.Contains("[LootForge]") != true &&
        Enumerable.Range(1, 8).Any(s => ParamHelper.GetCellInt(row, $"lotItemId0{s}") > 0 &&
            ParamHelper.GetCellInt(row, $"lotItemBasePoint0{s}") > 0);
    private sealed class Index
    {
        public readonly Dictionary<int, PARAM.Row> Rows;
        public readonly PARAM.Row[] Roots;
        public readonly Dictionary<int, int> Tails = new();
        public readonly HashSet<int> Exhausted = new();
        public int Cursor;
        public Index(PARAM param)
        {
            Rows = param.Rows.ToDictionary(r => r.ID);
            Roots = param.Rows.Where(IsOriginalRoot).ToArray();
        }
    }
    private static readonly ConditionalWeakTable<PARAM, Index> Indices = new();

    /// <summary>Count independent insertion rows after removing earlier generated chains.</summary>
    public static int Capacity(PARAM param)
    {
        var originals = param.Rows.Where(r => r.Name?.Contains("[LootForge]") != true).ToArray();
        var ids = originals.Select(r => r.ID).ToHashSet();
        var tails = new HashSet<int>();
        int available = 0;
        foreach (var row in originals)
        {
            if (!IsOriginalRoot(row)) continue;
            int tail = row.ID;
            while (tail < int.MaxValue && ids.Contains(tail + 1)) tail++;
            if (!tails.Add(tail)) continue;
            for (long next = (long)tail + 1; next < int.MaxValue && next / 10 == row.ID / 10 &&
                 !ids.Contains((int)next) && !ids.Contains((int)next + 1); next++) available++;
        }
        return Math.Min(available, Math.Max(0, ushort.MaxValue - originals.Length));
    }

    /// <summary>Append a fresh roll after the existing chain, leaving a gap before any unrelated lot.</summary>
    public static bool TryAppend(PARAM param, int baseId, int itemId, int category, ushort points, string label)
    {
        var index = Indices.GetValue(param, p => new Index(p));
        if (baseId <= 0 || param.Rows.Count >= ushort.MaxValue || index.Exhausted.Contains(baseId) || !index.Rows.ContainsKey(baseId)) return false;
        int tail = index.Tails.GetValueOrDefault(baseId, baseId);
        while (tail < int.MaxValue && index.Rows.ContainsKey(tail + 1)) tail++;
        // Existing routing reserves ten-ID blocks. Do not connect a previously
        // unreachable row on the far side of a gap or spill into the next block.
        long next = (long)tail + 1;
        if (next >= int.MaxValue || next / 10 != baseId / 10 || index.Rows.ContainsKey((int)next + 1))
        {
            index.Exhausted.Add(baseId);
            return false;
        }
        var row = new PARAM.Row((int)next, $"[LootForge] {label}", param.AppliedParamdef);
        // Construct from defaults, not an original row with one-shot flags,
        // accumulated lottery counters, luck or another item's quantity.
        var layout = ItemLotLayout.Extract(param);
        ParamHelper.SetCellFast(row, layout.ItemIdIndices[0], itemId);
        ParamHelper.SetCellFast(row, layout.CategoryIndices[0], category);
        ParamHelper.SetCellFast(row, layout.BasePointIndices[0], points);
        ParamHelper.SetCellFast(row, layout.NumIndices[0], (byte)1);
        ParamHelper.SetCellFast(row, layout.BasePointIndices[1], (ushort)(1000 - points));
        param.Rows.Add(row);
        index.Rows[row.ID] = row;
        index.Tails[baseId] = row.ID;
        return true;
    }

    /// <summary>Use a new independent roll on another existing lot when the requested chain is full.</summary>
    public static bool TryAppendAny(PARAM param, int itemId, int category, ushort points, string label)
    {
        var index = Indices.GetValue(param, p => new Index(p));
        while (index.Cursor < index.Roots.Length)
        {
            if (TryAppend(param, index.Roots[index.Cursor].ID, itemId, category, points, label)) return true;
            index.Cursor++;
        }
        return false;
    }
}
