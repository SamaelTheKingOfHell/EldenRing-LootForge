using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Cosmetic VFX copies with no inherited grease, status or buff mechanics.</summary>
public sealed class DiabloAuraService
{
    readonly Dictionary<string, int> generated = new();
    readonly PARAM visuals;
    readonly Dictionary<int, PARAM.Row> sources;
    int nextId = 8600000;

    public DiabloAuraService(Func<string, string?, PARAM> table)
    {
        visuals = table("SpEffectVfxParam", "SpEffectVfx");
        visuals.Rows.RemoveAll(row => row.Name?.StartsWith("[LootForge] Diablo Aura") == true);
        sources = visuals.ToRowDictionary();
    }

    public int Visual(string theme, bool weapon)
    {
        string key = theme + ":" + weapon;
        if (generated.TryGetValue(key, out int existing)) return existing;
        int source = weapon ? theme switch {
            "fire" => 62, "lightning" => 151, "glintstone" => 64,
            "holy" or "renewal" => 61, "frost" => 5092,
            "blood" => 5090, "poison" => 152, "rot" => 5094,
            _ => throw new InvalidDataException("Unknown Diablo aura: " + theme)
        } : theme switch {
            "fire" => 1645000, "lightning" => 1647000, "glintstone" => 1646000,
            "holy" => 1648000, "renewal" => 1643000, "frost" => 260,
            "blood" => 6, "poison" => 2, "rot" => 5,
            _ => throw new InvalidDataException("Unknown Diablo aura: " + theme)
        };
        if (!sources.TryGetValue(source, out var original))
            throw new InvalidDataException($"Diablo aura template {source} is missing.");
        while (sources.ContainsKey(nextId)) nextId++;
        var row = new PARAM.Row(original) { ID = nextId++, Name = "[LootForge] Diablo Aura " + key };
        // The live game buff wins the category when present. Copy only the VFX
        // row, never its source SpEffect's attack, status or buff-category fields.
        DiabloEffectService.Set(row, "playPriority", 255);
        foreach (var cell in row.Cells)
            if (cell.Def.InternalName is "initSfxId" or "finishSfxId" ||
                cell.Def.InternalName.EndsWith("SeId")) DiabloEffectService.Set(row, cell.Def.InternalName, -1);
        visuals.Rows.Add(row);
        sources[row.ID] = row;
        return generated[key] = row.ID;
    }
}
