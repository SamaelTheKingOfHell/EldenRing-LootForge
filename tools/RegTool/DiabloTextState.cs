using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Restore infusion text independently for every message archive and language.</summary>
public sealed class DiabloTextState
{
    public const string Filename = "lootforge_diablo_texts.json";
    public sealed class TextState
    {
        public string? Original { get; set; }
        public string? Applied { get; set; }
        public bool OriginalExists { get; set; }
        public bool AppliedExists { get; set; }
    }
    readonly Dictionary<string, Dictionary<string, Dictionary<int, TextState>>> saved;
    readonly Dictionary<string, HashSet<int>> requested = new();
    public bool HasHistory => saved.Count > 0;

    public DiabloTextState(string targetRegulation, List<FmgInjector.FmgTextSpec> specs, ISet<int>? infusedItems = null)
    {
        string path = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(targetRegulation))!, Filename);
        saved = File.Exists(path) ? JsonSerializer.Deserialize<Dictionary<string, Dictionary<string, Dictionary<int, TextState>>>>(File.ReadAllText(path))! : new();
        foreach (var spec in specs.Where(spec => spec.ItemId < 90000000 && (infusedItems == null || infusedItems.Contains(spec.ItemId))))
        {
            string category = spec.IsAccessory ? "Accessory" : spec.IsWeapon ? "Weapon" : "Protector";
            foreach (string suffix in new[] { "Name", "Info", "Caption" })
            {
                string name = category + suffix;
                if (!requested.TryGetValue(name, out var ids)) requested[name] = ids = new();
                ids.Add(spec.ItemId);
            }
        }
    }

    public void Prepare(BND4 archive, string identity)
    {
        if (requested.Count == 0 && !saved.ContainsKey(identity)) return;
        if (!saved.TryGetValue(identity, out var files)) saved[identity] = files = new();
        foreach (var file in archive.Files)
        {
            string name = Path.GetFileName(file.Name);
            var wanted = requested.FirstOrDefault(pair => FmgArchiveService.MatchesCategory(file.Name, pair.Key)).Value;
            if (!files.TryGetValue(name, out var states))
            {
                if (wanted == null) continue;
                files[name] = states = new();
            }
            var fmg = FMG.Read(file.Bytes);
            var entries = fmg.Entries.ToDictionary(entry => entry.ID);
            foreach (var (id, state) in states)
            {
                entries.TryGetValue(id, out var entry);
                if ((entry != null) == state.AppliedExists && entry?.Text == state.Applied)
                {
                    if (state.OriginalExists)
                    {
                        if (entry != null) entry.Text = state.Original;
                        else { entry = new FMG.Entry(id, state.Original); fmg.Entries.Add(entry); entries[id] = entry; }
                    }
                    else if (entry != null) { fmg.Entries.Remove(entry); entries.Remove(id); }
                }
                else { state.Original = entry?.Text; state.OriginalExists = entry != null; }
            }
            foreach (int id in wanted ?? new())
                if (!states.ContainsKey(id))
                {
                    entries.TryGetValue(id, out var entry);
                    states[id] = new() { Original = entry?.Text, OriginalExists = entry != null };
                }
            file.Bytes = fmg.Write();
        }
    }

    public void Observe(BND4 archive, string identity)
    {
        if (!saved.TryGetValue(identity, out var files)) return;
        foreach (var file in archive.Files)
        {
            if (!files.TryGetValue(Path.GetFileName(file.Name), out var states)) continue;
            var entries = FMG.Read(file.Bytes).Entries.ToDictionary(entry => entry.ID);
            foreach (var (id, state) in states)
            {
                entries.TryGetValue(id, out var entry);
                state.Applied = entry?.Text;
                state.AppliedExists = entry != null;
            }
        }
    }

    public void Stage(string stagedRegulation)
    {
        if (saved.Count > 0)
            File.WriteAllText(Path.Combine(Path.GetDirectoryName(stagedRegulation)!, Filename), JsonSerializer.Serialize(saved));
    }
}
