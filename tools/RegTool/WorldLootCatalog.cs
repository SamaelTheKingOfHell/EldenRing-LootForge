using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>World destinations proven by MSB treasure records and boss-death event code.</summary>
public sealed class WorldLootCatalog
{
    public record Destination(int LotId, string Name, EntityProgressionTier Tier, int FreeRows, string Evidence);
    public List<Destination> Chests { get; } = new();
    public List<Destination> Bosses { get; } = new();
    public List<Destination> Enemies { get; } = new();
    public List<ShopRangeCatalog.Shop> Merchants { get; } = new();
    public static Dictionary<int, string> Names(string defs, string table)
    {
        string path = Path.Combine(Path.GetDirectoryName(defs)!, "Names", table + ".txt");
        return !File.Exists(path) ? new() : File.ReadLines(path).Select(line => line.Split(' ', 2))
            .Where(parts => parts.Length == 2 && int.TryParse(parts[0], out _))
            .GroupBy(parts => int.Parse(parts[0])).ToDictionary(group => group.Key, group => group.First()[1]);
    }

    public static IEnumerable<string> Files(string profile, string? game, string relative, string pattern)
    {
        var paths = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (string root in new[] { game ?? "", profile })
        {
            string directory = Path.Combine(root, relative);
            if (!Directory.Exists(directory)) continue;
            foreach (string path in Directory.GetFiles(directory, pattern)) paths[Path.GetFileName(path)] = path;
        }
        return paths.OrderBy(pair => pair.Key).Select(pair => pair.Value);
    }

    /// <summary>Free contiguous slots after an original lot, leaving a separation gap.</summary>
    public static int FreeRows(PARAM param, int id)
    {
        var ids = param.Rows.Where(row => row.Name?.Contains("[LootForge]") != true).Select(row => row.ID).ToHashSet();
        int tail = id, free = 0;
        if (!ids.Contains(id)) return 0;
        while (ids.Contains(tail + 1)) tail++;
        while ((tail + 1) / 10 == id / 10 && !ids.Contains(tail + 2)) { free++; tail++; }
        return free;
    }

    public static EntityProgressionTier Tier(string map, string name)
    {
        var words = map.Split('_');
        if (words.Length >= 3 && words[0] is "m60" or "m61")
        {
            if (words[0] == "m61") return EntityProgressionTier.Endgame;
            int x = int.Parse(words[1]), y = int.Parse(words[2]);
            if (y >= 48) return EntityProgressionTier.Endgame;
            if (y >= 43 && x >= 41) return EntityProgressionTier.Late;
            if (y >= 40 || x >= 47) return EntityProgressionTier.Mid;
            return EntityProgressionTier.Early;
        }
        if (words.Length > 0 && words[0] is "m11" or "m16") return EntityProgressionTier.Late;
        if (words.Length > 0 && words[0] is "m12" or "m14") return EntityProgressionTier.Mid;
        if (words.Length > 0 && words[0] is "m13" or "m15" or "m19" or "m20" or "m21" or "m22" or "m28") return EntityProgressionTier.Endgame;
        return ProgressionTierClassifier.ClassifyTier(0, name);
    }

    public static WorldLootCatalog Load(string source, string? game, string defs, PARAM map, PARAM? enemy = null, PARAM? npc = null, PARAM? shops = null)
    {
        var catalog = new WorldLootCatalog();
        string profile = Path.GetDirectoryName(Path.GetFullPath(source))!;
        var rows = map.Rows.ToDictionary(row => row.ID);
        var names = Names(defs, "ItemLotParam_map");
        void Add(List<Destination> target, int id, string file, string proof)
        {
            if (id <= 0 || !rows.TryGetValue(id, out var row) || row.Name?.Contains("[LootForge]") == true ||
                (ReferenceEquals(target, catalog.Chests) && ParamHelper.GetCellInt(row, "getItemFlagId") <= 0) || target.Any(item => item.LotId / 10 == id / 10)) return;
            string name = names.GetValueOrDefault(id, file + " reward " + id);
            target.Add(new(id, name, Tier(file, name), FreeRows(map, id), proof));
        }
        var npcRows = npc?.Rows.ToDictionary(row => row.ID) ?? new();
        var enemyRows = enemy?.Rows.ToDictionary(row => row.ID) ?? new();
        var enemyNames = Names(defs, "ItemLotParam_enemy");
        foreach (string file in Files(profile, game, "map/MapStudio", "*.msb.dcx"))
        {
            var msb = MSBE.Read(file);
            foreach (var actor in msb.Parts.Enemies)
            {
                if (enemy == null || !npcRows.TryGetValue(actor.NPCParamID, out var character)) continue;
                int lot = ParamHelper.GetCellInt(character, "itemLotId_enemy");
                if (!enemyRows.TryGetValue(lot, out var drop)) continue;
                bool gear = false;
                for (int chain=lot; chain/10==lot/10 && enemyRows.TryGetValue(chain,out var part); chain++)
                    gear |= Enumerable.Range(1,8).Any(slot => ParamHelper.GetCellInt(part,$"lotItemCategory0{slot}") is 2 or 3 && ParamHelper.GetCellInt(part,$"lotItemId0{slot}") > 0);
                if (!gear) continue;
                string name = enemyNames.GetValueOrDefault(lot, actor.ModelName + " gear drop");
                var candidate = new Destination(lot, name, Tier(Path.GetFileName(file),name), FreeRows(enemy,lot), "MSB NPC gear-drop reference");
                var prior = catalog.Enemies.Find(item=>item.LotId==lot);
                if (prior == null) catalog.Enemies.Add(candidate);
                else if (candidate.Tier < prior.Tier) {catalog.Enemies.Remove(prior);catalog.Enemies.Add(candidate);}
            }
            foreach (var treasure in msb.Events.Treasures.Where(item => item.InChest == 1 && item.TreasurePartName != null))
                Add(catalog.Chests, treasure.ItemLotID, Path.GetFileName(file), "MSB InChest=1: " + treasure.TreasurePartName);
        }
        var scripts = Files(profile, game, "event", "*.emevd.dcx").ToArray();
        string? commonPath = scripts.FirstOrDefault(path => Path.GetFileName(path) == "common_func.emevd.dcx");
        var common = commonPath == null ? new Dictionary<long, EMEVD.Event>() : EMEVD.Read(commonPath).Events.ToDictionary(ev => ev.ID);
        static bool Boss(EMEVD.Event ev) => ev.Instructions.Any(ins => ins.Bank == 2003 && ins.ID == 12);
        void Rewards(EMEVD.Event ev, byte[]? arguments, string file)
        {
            foreach (var (ins, index) in ev.Instructions.Select((ins, index) => (ins, index)))
            {
                if (ins.Bank != 2003 || ins.ID is not (4 or 36) || ins.ArgData.Length < 4) continue;
                var parameter = ev.Parameters.FirstOrDefault(p => p.InstructionIndex == index && p.TargetStartByte == 0 && p.ByteCount == 4);
                if (parameter != null && (arguments == null || arguments.Length < parameter.SourceStartByte + 4)) continue;
                int id = parameter == null ? BitConverter.ToInt32(ins.ArgData, 0) : BitConverter.ToInt32(arguments!, (int)parameter.SourceStartByte);
                Add(catalog.Bosses, id, file, "EMEVD boss-defeat event " + ev.ID);
            }
        }
        foreach (string path in scripts.Where(path => Path.GetFileName(path).StartsWith('m')))
        {
            var script = EMEVD.Read(path);
            var local = script.Events.ToDictionary(ev => ev.ID);
            foreach (var ev in script.Events)
            {
                if (Boss(ev)) Rewards(ev, null, Path.GetFileName(path));
                foreach (var call in ev.Instructions.Where(ins => ins.Bank == 2000 && ins.ID is 0 or 6 && ins.ArgData.Length >= 8))
                {
                    long id = BitConverter.ToUInt32(call.ArgData, 4);
                    var definitions = call.ID == 6 ? common : local;
                    if (definitions.TryGetValue(id, out var definition) && Boss(definition))
                        Rewards(definition, call.ArgData[8..], Path.GetFileName(path));
                }
            }
        }
        if (names.TryGetValue(10000,out var margit) && margit.Contains("Margit"))
            Add(catalog.Bosses,10000,"", "Named Margit talisman-pouch boss reward");
        // Remembrance goods identify major-boss rewards even when their death and
        // award instructions live in separate events.
        var remembranceIds = Names(defs,"EquipParamGoods").Where(pair=>pair.Value.StartsWith("Remembrance of ") || pair.Value=="Elden Remembrance").Select(pair=>pair.Key).ToHashSet();
        foreach (var row in map.Rows)
            if (Enumerable.Range(1,8).Any(slot => ParamHelper.GetCellInt(row,$"lotItemCategory0{slot}")==1 && remembranceIds.Contains(ParamHelper.GetCellInt(row,$"lotItemId0{slot}"))))
                Add(catalog.Bosses, rows.ContainsKey(row.ID-row.ID%10) ? row.ID-row.ID%10 : row.ID, "", "Source remembrance reward");
        catalog.Merchants.AddRange(ShopRangeCatalog.Load(profile, game, defs, shops));
        return catalog;
    }
}
