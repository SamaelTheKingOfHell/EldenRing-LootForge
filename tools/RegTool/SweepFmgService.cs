using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Apply infusion text using indexed IDs while preserving each DLC archive's own entries.</summary>
public static class SweepFmgService
{
    /// <summary>Display changes for one infused item.</summary>
    public record Effect(int ItemId, string Category, string Rarity, string Description);

    /// <summary>Mutate all matching base/DLC FMGs without copying base archives over DLC content.</summary>
    public static void Apply(BND4 archive, List<Effect> effects)
    {
        foreach (var group in effects.GroupBy(e => e.Category))
        {
            var byId = new Dictionary<int, Effect>();
            foreach (var effect in group) byId[effect.ItemId] = effect;
            foreach (var file in archive.Files)
            {
                bool isName = FmgArchiveService.MatchesCategory(file.Name, group.Key + "Name");
                if (!isName && !FmgArchiveService.MatchesCategory(file.Name, group.Key + "Caption")) continue;
                var fmg = FMG.Read(file.Bytes);
                bool changed = false;
                foreach (var entry in fmg.Entries)
                {
                    if (string.IsNullOrWhiteSpace(entry.Text) || !byId.TryGetValue(entry.ID, out var effect)) continue;
                    if (isName && !entry.Text.StartsWith("["))
                    {
                        entry.Text = $"[{effect.Rarity.ToUpperInvariant()}] {entry.Text.Trim()}";
                        changed = true;
                    }
                    else if (!isName && !entry.Text.Contains("[Diablo"))
                    {
                        entry.Text = $"[Diablo {effect.Rarity}] {effect.Description}\n{entry.Text.Trim()}";
                        changed = true;
                    }
                }
                if (changed) file.Bytes = fmg.Write();
            }
        }
    }
}
