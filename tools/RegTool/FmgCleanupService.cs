using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Remove obsolete generated text without touching original or other-mod entries.</summary>
public static class FmgCleanupService
{
    /// <summary>Prune only IDs known to belong to removed LootForge equipment in each category.</summary>
    public static void Prune(BND4 archive, Dictionary<string, HashSet<int>> removed)
    {
        foreach (var file in archive.Files)
            foreach (var (category, ids) in removed)
            {
                if (ids.Count == 0 || !new[] { "Name", "Info", "Caption" }.Any(suffix => FmgArchiveService.MatchesCategory(file.Name, category + suffix))) continue;
                var fmg = FMG.Read(file.Bytes);
                if (fmg.Entries.RemoveAll(entry => ids.Contains(entry.ID)) > 0) file.Bytes = fmg.Write();
                break;
            }
    }
}
