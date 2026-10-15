using System.Text.Json;
using LootForge.RegTool;
using SoulsFormats;
using SoulsFormats.Cryptography;

/// <summary>Read-only comparison of original loot rows and generated accessory text in real profiles.</summary>
public static class ProfileAudit
{
    /// <summary>Write retained JSON evidence without modifying either regulation or its archives.</summary>
    public static void Run(string root, string source, string target, string report)
    {
        var original = RegulationDecryptor.DecryptERRegulation(source);
        var patched = RegulationDecryptor.DecryptERRegulation(target);
        PARAM Load(BND4 binder, string name, string definition)
        {
            var param = PARAM.Read(binder.Files.First(f => f.Name.EndsWith(name + ".param", StringComparison.OrdinalIgnoreCase)).Bytes);
            param.ApplyParamdefSomewhatCarefully(PARAMDEF.XmlDeserialize(Path.Combine(root, "tools/vendor/Paramdex/ER/Defs", definition + ".xml"), false, false));
            return param;
        }
        var loot = new Dictionary<string, object>();
        var equipmentIds = new Dictionary<int, HashSet<int>>();
        foreach (var (table, category) in new[] { ("EquipParamWeapon", 2), ("EquipParamProtector", 3), ("EquipParamAccessory", 4) })
            equipmentIds[category] = Load(patched, table, table).Rows.Select(r => r.ID).ToHashSet();
        foreach (string table in new[] { "ItemLotParam_enemy", "ItemLotParam_map" })
        {
            var before = Load(original, table, "ItemLotParam");
            var after = Load(patched, table, "ItemLotParam").Rows.ToDictionary(r => r.ID);
            var changed = new List<int>();
            int examined = 0;
            foreach (var row in before.Rows.Where(r => r.Name?.Contains("[LootForge]") != true))
            {
                examined++;
                if (!after.TryGetValue(row.ID, out var next) ||
                    JsonSerializer.Serialize(row.Cells.Select(c => c.Value)) != JsonSerializer.Serialize(next.Cells.Select(c => c.Value)))
                    changed.Add(row.ID);
            }
            var orphans = new List<object>();
            int orphanAccessories = 0;
            foreach (var row in after.Values)
                for (int slot = 1; slot <= 8; slot++)
                {
                    int id = ParamHelper.GetCellInt(row, $"lotItemId0{slot}");
                    int category = ParamHelper.GetCellInt(row, $"lotItemCategory0{slot}");
                    if (id <= 0 || !equipmentIds.TryGetValue(category, out var ids) || ids.Contains(id)) continue;
                    if (category == 4) orphanAccessories++;
                    if (orphans.Count < 15 || category == 4 && orphanAccessories < 15) orphans.Add(new { row = row.ID, slot, category, id });
                }
            loot[table] = new { examined, changed = changed.Count, firstChanged = changed.Take(12), orphanAccessories, orphanExamples = orphans };
        }
        var accessoryTable = Load(patched, "EquipParamAccessory", "EquipParamAccessory");
        var accessoryRows = accessoryTable.Rows.Where(r => r.Name?.Contains("[LootForge]") == true).ToArray();
        var accessories = accessoryRows.Select(r => r.ID).ToArray();
        bool BinaryLookup(int id)
        {
            int low = 0, high = accessoryTable.Rows.Count - 1;
            while (low <= high)
            {
                int middle = low + (high - low) / 2, candidate = accessoryTable.Rows[middle].ID;
                if (candidate == id) return true;
                if (candidate < id) low = middle + 1; else high = middle - 1;
            }
            return false;
        }
        var messages = new Dictionary<string, object>();
        string messageRoot = Path.Combine(Path.GetDirectoryName(target)!, "msg");
        if (Directory.Exists(messageRoot))
            foreach (string path in Directory.EnumerateFiles(messageRoot, "item*.msgbnd.dcx", SearchOption.AllDirectories))
            {
                var binder = BND4.Read(path);
                foreach (var file in binder.Files.Where(f => FmgArchiveService.MatchesCategory(f.Name, "AccessoryName")))
                {
                    var names = FMG.Read(file.Bytes).Entries.ToDictionary(e => e.ID, e => e.Text);
                    var missing = accessories.Where(id => !names.TryGetValue(id, out var text) || !FmgInjector.IsValidFmgText(text)).ToArray();
                    messages[Path.GetRelativePath(messageRoot, path) + "/" + Path.GetFileName(file.Name)] = new { entries = names.Count, missing = missing.Length, firstMissing = missing.Take(12) };
                }
            }
        File.WriteAllText(report, JsonSerializer.Serialize(new { source, target, loot, accessoryCount = accessories.Length,
            firstAccessories = accessoryRows.Take(12).Select(r => new { r.ID, icon = ParamHelper.GetCellInt(r, "iconId"), reference = ParamHelper.GetCellInt(r, "refId"), sort = ParamHelper.GetCellInt(r, "sortId") }),
            invalidIcons = accessoryRows.Count(r => ParamHelper.GetCellInt(r, "iconId") <= 0),
            outOfOrderAccessories = accessoryTable.Rows.Zip(accessoryTable.Rows.Skip(1)).Count(pair => pair.First.ID >= pair.Second.ID),
            firstUnsorted = accessoryTable.Rows.Zip(accessoryTable.Rows.Skip(1)).Where(pair => pair.First.ID >= pair.Second.ID).Take(4).Select(pair => new { before = pair.First.ID, after = pair.Second.ID }),
            binaryLookupMisses = accessories.Count(id => !BinaryLookup(id)), firstBinaryMisses = accessories.Where(id => !BinaryLookup(id)).Take(12),
            messages }, new JsonSerializerOptions { WriteIndented = true }));
    }
}
