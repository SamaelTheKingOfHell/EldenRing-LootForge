using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service providing diagnostic verification, regulation dumps, FMG search dumps,
    /// and clean game message extraction from Data0.bdt archives.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class DiagnosticService
    {
        public static int ExecuteVerify(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path.");
                return 1;
            }

            if (!File.Exists(inputPath))
            {
                Console.Error.WriteLine($"Input regulation file not found: {inputPath}");
                return 1;
            }

            Console.WriteLine($"Decrypting: {inputPath}");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);
            Console.WriteLine($"Decryption successful. BND contains {bnd.Files.Count} param files.");
            return 0;
        }

        public static int ExecuteDumpFmg(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to item.msgbnd.dcx.");
                return 1;
            }

            if (!File.Exists(inputPath))
            {
                Console.Error.WriteLine($"File not found: {inputPath}");
                return 1;
            }

            Console.WriteLine($"[RegTool] Loading BND4: {inputPath} (size: {new FileInfo(inputPath).Length} bytes)...");
            BND4 bnd = BND4.Read(inputPath);
            Console.WriteLine($"[RegTool] BND4 contains {bnd.Files.Count} files.");

            string searchQuery = options.TryGetValue("search", out string? sq) ? sq : "";

            if (options.TryGetValue("export-json", out string? exportJson) && !string.IsNullOrEmpty(exportJson))
            {
                var dict = new Dictionary<string, Dictionary<int, string>>();
                foreach (var file in bnd.Files)
                {
                    string fname = Path.GetFileNameWithoutExtension(file.Name ?? "");
                    if (fname.Equals("WeaponName", StringComparison.OrdinalIgnoreCase) ||
                        fname.Equals("ProtectorName", StringComparison.OrdinalIgnoreCase) ||
                        fname.Equals("AccessoryName", StringComparison.OrdinalIgnoreCase))
                    {
                        var fmg = FMG.Read(file.Bytes);
                        var entries = new Dictionary<int, string>();
                        foreach (var e in fmg.Entries)
                        {
                            if (!string.IsNullOrWhiteSpace(e.Text))
                                entries[e.ID] = e.Text;
                        }
                        dict[fname] = entries;
                    }
                }
                File.WriteAllText(exportJson, System.Text.Json.JsonSerializer.Serialize(dict, new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
                Console.WriteLine($"[RegTool] Exported FMG entries to {exportJson}");
                return 0;
            }

            foreach (var file in bnd.Files)
            {
                string fname = Path.GetFileName(file.Name ?? "???");
                if (!fname.EndsWith(".fmg", StringComparison.OrdinalIgnoreCase)) continue;

                FMG fmg = FMG.Read(file.Bytes);
                if (!string.IsNullOrEmpty(searchQuery))
                {
                    var matches = fmg.Entries.Where(e => e.Text != null && e.Text.Contains(searchQuery, StringComparison.OrdinalIgnoreCase)).ToList();
                    if (int.TryParse(searchQuery, out int sId))
                    {
                        var idMatch = fmg.Entries.FirstOrDefault(e => e.ID == sId);
                        if (idMatch != null && !matches.Contains(idMatch)) matches.Add(idMatch);
                    }
                    if (matches.Count > 0)
                    {
                        Console.WriteLine($"  {fname,-30} Search='{searchQuery}' Matches: {matches.Count}");
                        foreach (var entry in matches.Take(15))
                        {
                            string text = entry.Text ?? "<null>";
                            if (text.Length > 80) text = text.Substring(0, 80) + "...";
                            Console.WriteLine($"    [{entry.ID}] {text}");
                        }
                    }
                }
                else
                {
                    var highEntries = fmg.Entries.Where(e => e.ID >= 9000000).ToList();
                    Console.WriteLine($"  {fname,-30} Version={fmg.Version,-12} Total={fmg.Entries.Count,6}  ID>=9M: {highEntries.Count}");
                    foreach (var entry in highEntries)
                    {
                        string text = entry.Text ?? "<null>";
                        if (text.Length > 80) text = text.Substring(0, 80) + "...";
                        Console.WriteLine($"    [{entry.ID}] {text}");
                    }
                }
            }
            return 0;
        }

        public static int ExecuteDumpReg(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to regulation.bin.");
                return 1;
            }
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";

            Console.WriteLine($"[RegTool] Decrypting regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            void InspectTable(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) return;
                var param = PARAM.Read(file.Bytes);
                string defBaseName = tableName.StartsWith("ItemLotParam", StringComparison.OrdinalIgnoreCase) ? "ItemLotParam" : tableName;
                string xmlFile = Path.Combine(defsDir, $"{defBaseName}.xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }

                Console.WriteLine($"\n=== {tableName} (total rows: {param.Rows.Count}) ===");
                if (tableName == "ShopLineupParam")
                {
                    var interesting = param.Rows.Where(r => (r.ID >= 100500 && r.ID <= 100524) || r.ID >= 9000000 || (r.Name != null && r.Name.Contains("LootForge"))).ToList();
                    Console.WriteLine($"Found {interesting.Count} matching rows:");
                    foreach (var r in interesting)
                    {
                        int eqId = ParamHelper.GetCellInt(r, "equipId");
                        int eqType = ParamHelper.GetCellInt(r, "equipType");
                        int val = ParamHelper.GetCellInt(r, "value");
                        int icon = ParamHelper.GetCellInt(r, "iconId");
                        int nameMsg = ParamHelper.GetCellInt(r, "nameMsgId");
                        Console.WriteLine($"  ID={r.ID} Name='{r.Name}' equipId={eqId} equipType={eqType} value={val} iconId={icon} nameMsgId={nameMsg}");
                    }
                }

                else if (tableName == "EquipParamProtector")
                {
                    var injected = param.Rows.Where(r => r.ID >= 9000000 || (r.Name != null && r.Name.Contains("LootForge"))).ToList();
                    var badIcons = injected.Where(r => {
                        int m = ParamHelper.GetCellInt(r, "iconIdM");
                        int f = ParamHelper.GetCellInt(r, "iconIdF");
                        return m <= 0 || m == 3141 || m == 3142 || f <= 0 || f == 3141 || f == 3142;
                    }).ToList();

                    Console.WriteLine($"Injected EquipParamProtector rows: {injected.Count} (Invalid placeholder icons: {badIcons.Count})");
                    if (badIcons.Count > 0)
                    {
                        Console.WriteLine($"[RegTool WARN] Found {badIcons.Count} protector rows with invalid icons:");
                        foreach (var r in badIcons.Take(10))
                        {
                            int iconM = ParamHelper.GetCellInt(r, "iconIdM");
                            int iconF = ParamHelper.GetCellInt(r, "iconIdF");
                            Console.WriteLine($"  ID={r.ID} Name='{r.Name}' iconM={iconM} iconF={iconF}");
                        }
                    }
                    else
                    {
                        Console.WriteLine("[RegTool SUCCESS] All injected protector rows have authentic retail icons!");
                    }

                    var vanillaMaiden = param.Rows.Where(r => r.ID >= 902000 && r.ID <= 903200).ToList();
                    foreach (var r in vanillaMaiden)
                    {
                        int iconM = ParamHelper.GetCellInt(r, "iconIdM");
                        int iconF = ParamHelper.GetCellInt(r, "iconIdF");
                        int model = ParamHelper.GetCellInt(r, "equipModelId");
                        Console.WriteLine($"  [Vanilla Maiden] ID={r.ID} Name='{r.Name}' iconM={iconM} iconF={iconF} model={model}");
                    }

                    // Print short skirts rows
                    foreach (var r in injected.Where(r => r.Name != null && r.Name.Contains("short skirts", StringComparison.OrdinalIgnoreCase)))
                    {
                        int iconM = ParamHelper.GetCellInt(r, "iconIdM");
                        int iconF = ParamHelper.GetCellInt(r, "iconIdF");
                        int model = ParamHelper.GetCellInt(r, "equipModelId");
                        int cat = ParamHelper.GetCellInt(r, "protectorCategory");
                        Console.WriteLine($"  [Skirt Row] ID={r.ID} Name='{r.Name}' iconM={iconM} iconF={iconF} model={model} cat={cat}");
                    }
                }
                else if (tableName == "EquipParamWeapon")
                {
                    var interesting = param.Rows.Where(r => r.ID >= 9000000 || (r.Name != null && r.Name.Contains("LootForge"))).ToList();
                    Console.WriteLine($"Found {interesting.Count} matching rows in EquipParamWeapon:");
                    foreach (var r in interesting)
                    {
                        int icon = ParamHelper.GetCellInt(r, "iconId");
                        Console.WriteLine($"  ID={r.ID} Name='{r.Name}' icon={icon}");
                    }
                }
                else if (tableName == "ItemLotParam_enemy")
                {
                    string search = options.TryGetValue("search", out string? sVal) ? sVal : "";
                    var interesting = !string.IsNullOrEmpty(search)
                        ? param.Rows.Where(r => r.Name != null && r.Name.Contains(search, StringComparison.OrdinalIgnoreCase)).ToList()
                        : param.Rows.Where(r => r.ID >= 9000000 || (r.Name != null && (r.Name.Contains("Godrick") || r.Name.Contains("Noble") || r.Name.Contains("Soldier") || r.Name.Contains("Wolf")))).ToList();
                    Console.WriteLine($"Found {interesting.Count} matching rows in ItemLotParam_enemy:");
                    foreach (var r in interesting.Take(40))
                    {
                        Console.WriteLine($"  ID={r.ID} Name='{r.Name}'");
                        for (int s = 1; s <= 8; s++)
                        {
                            int item = ParamHelper.GetCellInt(r, $"lotItemId0{s}");
                            if (item > 0)
                            {
                                int cat = ParamHelper.GetCellInt(r, $"lotItemCategory0{s}");
                                int pts = ParamHelper.GetCellInt(r, $"lotItemBasePoint0{s}");
                                int num = ParamHelper.GetCellInt(r, $"lotItemNum0{s}");
                                int flag = ParamHelper.GetCellInt(r, $"getItemFlagId0{s}");
                                Console.WriteLine($"    Slot {s}: item={item} cat={cat} pts={pts} num={num} flag={flag}");
                            }
                        }
                    }
                }
                else if (tableName == "NpcParam")
                {
                    string search = options.TryGetValue("search", out string? sVal) ? sVal : "Soldier";
                    var interesting = param.Rows.Where(r => r.Name != null && r.Name.Contains(search, StringComparison.OrdinalIgnoreCase)).Take(10).ToList();
                    Console.WriteLine($"Found {interesting.Count} matching rows in NpcParam:");
                    foreach (var r in interesting)
                    {
                        int lot = ParamHelper.GetCellInt(r, "itemLotId_enemy");
                        Console.WriteLine($"  ID={r.ID} Name='{r.Name}' itemLotId_enemy={lot}");
                    }
                }
            }

            InspectTable("ShopLineupParam");
            InspectTable("EquipParamProtector");
            InspectTable("EquipParamWeapon");
            InspectTable("ItemLotParam_enemy");
            InspectTable("NpcParam");
            return 0;
        }

        public static int ExecuteFindItem(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to regulation.bin.");
                return 1;
            }
            if (!options.TryGetValue("item", out string? itemStr) || !int.TryParse(itemStr, out int targetItemId))
            {
                Console.Error.WriteLine("Missing or invalid --item <id>.");
                return 1;
            }
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";

            Console.WriteLine($"[RegTool] Decrypting regulation: {inputPath} to search for item ID {targetItemId}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            PARAM LoadParam(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) throw new Exception($"Table {tableName} not found");
                var param = PARAM.Read(file.Bytes);
                string defBaseName = tableName.StartsWith("ItemLotParam", StringComparison.OrdinalIgnoreCase) ? "ItemLotParam" : tableName;
                string xmlFile = Path.Combine(defsDir, $"{defBaseName}.xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }
                return param;
            }

            var matchedLotIds = new HashSet<int>();

            void SearchLotTable(string tableName)
            {
                var param = LoadParam(tableName);
                Console.WriteLine($"\n--- Searching {tableName} (rows: {param.Rows.Count}) for item {targetItemId} ---");
                foreach (var r in param.Rows)
                {
                    bool found = false;
                    for (int s = 1; s <= 8; s++)
                    {
                        int itm = ParamHelper.GetCellInt(r, $"lotItemId0{s}");
                        if (itm == targetItemId)
                        {
                            found = true;
                            break;
                        }
                    }

                    if (found)
                    {
                        matchedLotIds.Add(r.ID);
                        Console.WriteLine($"[MATCH] {tableName} Row ID={r.ID} Name='{r.Name}'");
                        for (int s = 1; s <= 8; s++)
                        {
                            int itm = ParamHelper.GetCellInt(r, $"lotItemId0{s}");
                            if (itm > 0)
                            {
                                int cat = ParamHelper.GetCellInt(r, $"lotItemCategory0{s}");
                                int pts = ParamHelper.GetCellInt(r, $"lotItemBasePoint0{s}");
                                int num = ParamHelper.GetCellInt(r, $"lotItemNum0{s}");
                                int flag = ParamHelper.GetCellInt(r, $"getItemFlagId0{s}");
                                Console.WriteLine($"   Slot {s}: item={itm} category={cat} basePoint={pts} num={num} flag={flag}");
                            }
                        }

                        // Also check chained rows (ID + 1 .. ID + 9)
                        for (int offset = 1; offset <= 9; offset++)
                        {
                            var chained = param.Rows.FirstOrDefault(row => row.ID == r.ID + offset);
                            if (chained != null)
                            {
                                Console.WriteLine($"   [Chained Row +{offset}] ID={chained.ID} Name='{chained.Name}'");
                                for (int s = 1; s <= 8; s++)
                                {
                                    int itm = ParamHelper.GetCellInt(chained, $"lotItemId0{s}");
                                    if (itm > 0)
                                    {
                                        int cat = ParamHelper.GetCellInt(chained, $"lotItemCategory0{s}");
                                        int pts = ParamHelper.GetCellInt(chained, $"lotItemBasePoint0{s}");
                                        int num = ParamHelper.GetCellInt(chained, $"lotItemNum0{s}");
                                        int flag = ParamHelper.GetCellInt(chained, $"getItemFlagId0{s}");
                                        Console.WriteLine($"      Slot {s}: item={itm} category={cat} basePoint={pts} num={num} flag={flag}");
                                    }
                                }
                            }
                        }
                    }
                }
            }

            SearchLotTable("ItemLotParam_enemy");
            SearchLotTable("ItemLotParam_map");

            // Now search NpcParam to find which NPC drops this ItemLot
            var npcParam = LoadParam("NpcParam");
            Console.WriteLine($"\n--- Checking NpcParam for matching ItemLot IDs ---");
            foreach (var r in npcParam.Rows)
            {
                int lotId = ParamHelper.GetCellInt(r, "itemLotId_enemy");
                if (matchedLotIds.Contains(lotId))
                {
                    Console.WriteLine($"[NPC MATCH] NpcParam ID={r.ID} Name='{r.Name}' itemLotId_enemy={lotId}");
                }
            }

            return 0;
        }

        public static int ExecuteDumpBossLots(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath)) return 1;
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            PARAM LoadParam(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) throw new Exception($"Table {tableName} not found");
                var param = PARAM.Read(file.Bytes);
                string defBaseName = tableName.StartsWith("ItemLotParam", StringComparison.OrdinalIgnoreCase) ? "ItemLotParam" : tableName;
                string xmlFile = Path.Combine(defsDir, $"{defBaseName}.xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }
                return param;
            }

            var mapParam = LoadParam("ItemLotParam_map");
            var enemyParam = LoadParam("ItemLotParam_enemy");

            Console.WriteLine($"=== Scanning for 100% Guaranteed Drops (Bosses & Pickups) ===");
            int mapBossCount = 0;
            foreach (var r in mapParam.Rows)
            {
                int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                int cat1 = ParamHelper.GetCellInt(r, "lotItemCategory01");
                // Check if category is Weapon (2), Protector (3), or Accessory (4) with 1000 points
                if (itm1 > 0 && p1 >= 1000 && (cat1 == 2 || cat1 == 4))
                {
                    mapBossCount++;
                    if (mapBossCount <= 40 || r.ID == 1037420400)
                    {
                        Console.WriteLine($"[MAP BOSS/REWARD] ID={r.ID} Name='{r.Name}' Item={itm1} Cat={cat1} Pts={p1}");
                    }
                }
            }
            Console.WriteLine($"Total 100% Weapon/Accessory drops in ItemLotParam_map: {mapBossCount}");

            int enemyBossCount = 0;
            foreach (var r in enemyParam.Rows)
            {
                int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                int cat1 = ParamHelper.GetCellInt(r, "lotItemCategory01");
                if (itm1 > 0 && p1 >= 1000 && (cat1 == 2 || cat1 == 4))
                {
                    enemyBossCount++;
                    if (enemyBossCount <= 40)
                    {
                        Console.WriteLine($"[ENEMY BOSS/REWARD] ID={r.ID} Name='{r.Name}' Item={itm1} Cat={cat1} Pts={p1}");
                    }
                }
            }
            Console.WriteLine($"Total 100% Weapon/Accessory drops in ItemLotParam_enemy: {enemyBossCount}");
            return 0;
        }

        public static int ExecuteFindMultiSlotLots(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath)) return 1;
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            PARAM LoadParam(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) throw new Exception($"Table {tableName} not found");
                var param = PARAM.Read(file.Bytes);
                string xmlFile = Path.Combine(defsDir, "ItemLotParam.xml");
                if (File.Exists(xmlFile))
                {
                    var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    param.ApplyParamdefSomewhatCarefully(def);
                }
                return param;
            }

            void InspectMulti(string tableName)
            {
                var param = LoadParam(tableName);
                Console.WriteLine($"\n=== {tableName}: Rows with multiple slots filled ===");
                int count = 0;
                foreach (var r in param.Rows)
                {
                    int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                    int itm2 = ParamHelper.GetCellInt(r, "lotItemId02");
                    int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                    int p2 = ParamHelper.GetCellInt(r, "lotItemBasePoint02");
                    if (itm1 > 0 && itm2 > 0)
                    {
                        count++;
                        if (count <= 25)
                        {
                            Console.WriteLine($"Row ID={r.ID} Name='{r.Name}'");
                            for (int s = 1; s <= 8; s++)
                            {
                                int itm = ParamHelper.GetCellInt(r, $"lotItemId0{s}");
                                if (itm > 0)
                                {
                                    int cat = ParamHelper.GetCellInt(r, $"lotItemCategory0{s}");
                                    int pts = ParamHelper.GetCellInt(r, $"lotItemBasePoint0{s}");
                                    int num = ParamHelper.GetCellInt(r, $"lotItemNum0{s}");
                                    int flag = ParamHelper.GetCellInt(r, $"getItemFlagId0{s}");
                                    Console.WriteLine($"   Slot {s}: item={itm} cat={cat} pts={pts} num={num} flag={flag}");
                                }
                            }
                        }
                    }
                }
                Console.WriteLine($"Total rows with multiple slots in {tableName}: {count}");
            }

            InspectMulti("ItemLotParam_map");
            InspectMulti("ItemLotParam_enemy");
            return 0;
        }

        public static int ExecuteDumpEmevd(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath)) return 1;
            EMEVD emevd = EMEVD.Read(inputPath);
            Console.WriteLine($"[EMEVD] Loaded {inputPath}, total events: {emevd.Events.Count}");
            foreach (var ev in emevd.Events)
            {
                foreach (var ins in ev.Instructions)
                {
                    if (ins.Bank == 2003 && ins.ID == 66)
                    {
                        int lotId = BitConverter.ToInt32(ins.ArgData, 4);
                        Console.WriteLine($"[AWARD ITEM LOT] Event {ev.ID}: lotId={lotId}");
                    }
                }
            }
            return 0;
        }

        public static int ExtractMsgFiles(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("game-dir", out string? gameDir) || string.IsNullOrEmpty(gameDir))
            {
                Console.WriteLine("[RegTool ERROR] --game-dir required for extract-msg command");
                return 1;
            }

            if (!options.TryGetValue("output", out string? outputDir) || string.IsNullOrEmpty(outputDir))
            {
                Console.WriteLine("[RegTool ERROR] --output required for extract-msg command");
                return 1;
            }

            string bhdPath = Path.Combine(gameDir, "Data0.bhd");
            string bdtPath = Path.Combine(gameDir, "Data0.bdt");

            if (!File.Exists(bhdPath) || !File.Exists(bdtPath))
            {
                Console.WriteLine($"[RegTool ERROR] Data0 archives not found in: {gameDir}");
                return 1;
            }

            try
            {
                Console.WriteLine($"[RegTool] Reading BXF4 archive: Data0.bhd + Data0.bdt...");
                BXF4 bxf = BXF4.Read(bhdPath, bdtPath);
                foreach (var file in bxf.Files)
                {
                    byte[] fileData = file.Bytes;
                    if (fileData.Length > 4 && fileData[0] == 'D' && fileData[1] == 'C' && fileData[2] == 'X')
                    {
                        try
                        {
                            BND4 bnd = BND4.Read(fileData);
                            var fmgFiles = bnd.Files.Where(f => f.Name != null && f.Name.EndsWith(".fmg", StringComparison.OrdinalIgnoreCase)).ToList();
                            if (fmgFiles.Any(f => f.Name.Contains("Weapon", StringComparison.OrdinalIgnoreCase) || f.Name.Contains("Protector", StringComparison.OrdinalIgnoreCase)))
                            {
                                string engUSDir = Path.Combine(outputDir, "engUS");
                                Directory.CreateDirectory(engUSDir);
                                string outputPath = Path.Combine(engUSDir, "item.msgbnd.dcx");
                                File.WriteAllBytes(outputPath, fileData);
                                Console.WriteLine($"[RegTool SUCCESS] Extracted item.msgbnd.dcx to: {outputPath}");
                                return 0;
                            }
                        }
                        catch { }
                    }
                }
                Console.WriteLine("[RegTool WARN] Could not find item.msgbnd.dcx in Data0.bdt");
                return 1;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool ERROR] {ex.Message}");
                return 1;
            }
        }
    }
}
