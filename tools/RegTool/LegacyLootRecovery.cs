using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool;

/// <summary>Recover original empty/no-drop slots changed by older LootForge versions, using a matching backup.</summary>
public static class LegacyLootRecovery
{
    private static readonly HashSet<string> ModifiedTables = new(StringComparer.OrdinalIgnoreCase)
    {
        "EquipParamWeapon.param", "EquipParamProtector.param", "EquipParamAccessory.param",
        "ItemLotParam_enemy.param", "ItemLotParam_map.param", "ShopLineupParam.param",
        "SpEffectParam.param", "SwordArtsParam.param", "BehaviorParam_PC.param", "AtkParam_Pc.param"
    };

    /// <summary>Only restore a slot when all unrelated source data matches a clean backup.</summary>
    public static int Restore(BND4 source, Func<string, string, (PARAM Param, BinderFile File)> load, string backupDirectory, string defs)
    {
        var owned = new Dictionary<int, HashSet<int>>();
        foreach (var (table, category) in new[] { ("EquipParamWeapon", 2), ("EquipParamProtector", 3), ("EquipParamAccessory", 4) })
            owned[category] = load(table, table).Param.Rows.Where(r => r.Name?.Contains("[LootForge]") == true).Select(r => r.ID).ToHashSet();
        if (owned.Values.All(ids => ids.Count == 0)) return 0;
        var affected = new Dictionary<string, List<(PARAM.Row Row, HashSet<string> Fields)>>();
        foreach (string table in new[] { "ItemLotParam_enemy", "ItemLotParam_map" })
        {
            var rows = new List<(PARAM.Row, HashSet<string>)>();
            foreach (var row in load(table, "ItemLotParam").Param.Rows.Where(r => r.Name?.Contains("[LootForge]") != true))
            {
                var fields = new HashSet<string>();
                for (int slot = 1; slot <= 8; slot++)
                {
                    int category = ParamHelper.GetCellInt(row, $"lotItemCategory0{slot}");
                    if (!owned.TryGetValue(category, out var ids) || !ids.Contains(ParamHelper.GetCellInt(row, $"lotItemId0{slot}"))) continue;
                    foreach (string prefix in new[] { "lotItemId", "lotItemCategory", "lotItemBasePoint", "lotItemNum", "getItemFlagId" })
                        fields.Add($"{prefix}0{slot}");
                }
                if (fields.Count > 0) rows.Add((row, fields));
            }
            affected[table] = rows;
        }
        if (affected.Values.All(rows => rows.Count == 0)) return 0;
        if (!Directory.Exists(backupDirectory)) throw new InvalidDataException("Legacy mixed loot needs its original pre-forge backup to recover original drop chances.");
        var files = source.Files.Where(f => !ModifiedTables.Contains(Path.GetFileName(f.Name))).ToDictionary(f => f.Name, f => f.Bytes);
        foreach (string path in Directory.EnumerateFiles(backupDirectory, "regulation.bin.bak_*").OrderDescending())
        {
            BND4 backup;
            try { backup = RegulationDecryptor.DecryptERRegulation(path); }
            catch { continue; }
            var candidates = backup.Files.ToDictionary(f => f.Name);
            if (files.Any(f => !candidates.TryGetValue(f.Key, out var candidate) || !f.Value.AsSpan().SequenceEqual(candidate.Bytes))) continue;
            if (backup.Files.Count != source.Files.Count) continue;
            if (backup.Files.Where(f => new[] { "EquipParamAccessory.param", "EquipParamWeapon.param", "EquipParamProtector.param" }
                .Any(table => f.Name.EndsWith(table, StringComparison.OrdinalIgnoreCase)))
                .Any(f => PARAM.Read(f.Bytes).Rows.Any(r => r.Name?.Contains("[LootForge]") == true))) continue;
            var changes = new List<(PARAM.Cell Cell, object Value)>();
            bool matches = true;
            foreach (var (table, rows) in affected)
            {
                var file = backup.Files.First(f => f.Name.EndsWith(table + ".param", StringComparison.OrdinalIgnoreCase));
                var original = PARAM.Read(file.Bytes);
                original.ApplyParamdefSomewhatCarefully(PARAMDEF.XmlDeserialize(Path.Combine(defs, "ItemLotParam.xml"), false, false));
                var originals = original.Rows.ToDictionary(r => r.ID);
                foreach (var (row, fields) in rows)
                {
                    if (!originals.TryGetValue(row.ID, out var before)) { matches = false; break; }
                    for (int i = 0; i < row.Cells.Count; i++)
                    {
                        var cell = row.Cells[i];
                        if (fields.Contains(cell.Def.InternalName)) changes.Add((cell, before.Cells[i].Value));
                        else if (!System.Collections.StructuralComparisons.StructuralEqualityComparer.Equals(cell.Value, before.Cells[i].Value))
                        { matches = false; break; }
                    }
                    if (!matches) break;
                }
                if (!matches) break;
            }
            if (!matches) continue;
            foreach (var (cell, value) in changes) cell.Value = value;
            Console.WriteLine($"[RegTool] Restored {affected.Values.Sum(rows => rows.Count)} legacy mixed loot rows from verified backup {Path.GetFileName(path)}.");
            return affected.Values.Sum(rows => rows.Count);
        }
        throw new InvalidDataException("No matching clean pre-forge backup was found for legacy mixed loot. Existing loot cannot be safely reconstructed from this patched regulation.");
    }
}
