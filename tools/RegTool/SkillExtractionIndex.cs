using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Index source dependencies once instead of scanning whole tables for each selected weapon.</summary>
public sealed class SkillExtractionIndex
{
    public Dictionary<int, PARAM.Row> Skills { get; } = new();
    public Dictionary<int, List<PARAM.Row>> Behaviors { get; } = new();
    public Dictionary<int, PARAM.Row> Attacks { get; } = new();

    /// <summary>Preserve first-row lookup semantics and group behaviors by their actual variation ID.</summary>
    public SkillExtractionIndex(PARAM skills, PARAM behaviors, PARAM? attacks)
    {
        foreach (var row in skills.Rows) Skills.TryAdd(row.ID, row);
        foreach (var row in behaviors.Rows)
        {
            int variation = ParamHelper.GetCellInt(row, "variationId");
            if (!Behaviors.TryGetValue(variation, out var group))
                Behaviors[variation] = group = new();
            group.Add(row);
        }
        if (attacks != null)
            foreach (var row in attacks.Rows) Attacks.TryAdd(row.ID, row);
    }
}
