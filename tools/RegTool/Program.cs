using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    class Program
    {
        static int Main(string[] args)
        {
            if (args.Length == 0 || args[0] == "--help" || args[0] == "-h")
            {
                PrintUsage();
                return 0;
            }

            string command = args[0].ToLowerInvariant();
            var options = ParseArguments(args.Skip(1).ToArray());

            try
            {
                switch (command)
                {
                    case "patch":
                        return ExecutePatch(options);
                    case "verify":
                        return ExecuteVerify(options);
                    case "extract-msg":
                        return ExtractMsgFiles(options);
                    default:
                        Console.Error.WriteLine($"Unknown command: '{command}'");
                        PrintUsage();
                        return 1;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[RegTool ERROR] {ex.Message}");
                Console.Error.WriteLine(ex.StackTrace);
                return 2;
            }
        }

        static void PrintUsage()
        {
            Console.WriteLine("LootForge Regulation Tool (RegTool)");
            Console.WriteLine("Usage:");
            Console.WriteLine("  RegTool patch --input <source_reg> --output <target_reg> --defs <paramdex_defs> --spec <patch_spec.json> [--msg <game_msg_engUS_dir>]");
            Console.WriteLine("  RegTool verify --input <regulation.bin>");
            Console.WriteLine("  RegTool extract-msg --game-dir <elden_ring_game_dir> --output <backup_msg_dir>");
        }

        static Dictionary<string, string> ParseArguments(string[] args)
        {
            var dict = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i].StartsWith("--") && i + 1 < args.Length && !args[i + 1].StartsWith("--"))
                {
                    string key = args[i].Substring(2).ToLowerInvariant();
                    dict[key] = args[i + 1];
                    i++;
                }
            }
            return dict;
        }

        static int ExecuteVerify(Dictionary<string, string> options)
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

        static int ExtractMsgFiles(Dictionary<string, string> options)
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

            if (!File.Exists(bhdPath))
            {
                Console.WriteLine($"[RegTool ERROR] Data0.bhd not found at: {bhdPath}");
                return 1;
            }

            if (!File.Exists(bdtPath))
            {
                Console.WriteLine($"[RegTool ERROR] Data0.bdt not found at: {bdtPath}");
                return 1;
            }

            try
            {
                Console.WriteLine($"[RegTool] Reading BXF4 archive: Data0.bhd + Data0.bdt...");
                BXF4 bxf = BXF4.Read(bhdPath, bdtPath);

                Console.WriteLine($"[RegTool] Archive contains {bxf.Files.Count} files. Searching for item.msgbnd.dcx...");

                int extracted = 0;

                foreach (var file in bxf.Files)
                {
                    try
                    {
                        byte[] fileData = file.Bytes;

                        // Check if this is a DCX-compressed file
                        if (fileData.Length > 4 && fileData[0] == 'D' && fileData[1] == 'C' && fileData[2] == 'X')
                        {
                            // Try to read as BND4
                            BND4 bnd = BND4.Read(fileData);

                            // Check if it contains .fmg files
                            var fmgFiles = bnd.Files.Where(f => f.Name != null && f.Name.EndsWith(".fmg", StringComparison.OrdinalIgnoreCase)).ToList();

                            if (fmgFiles.Count > 0)
                            {
                                // Check if this is item.msgbnd.dcx by looking at FMG names
                                bool isItemMsg = fmgFiles.Any(f =>
                                    f.Name.Contains("Weapon", StringComparison.OrdinalIgnoreCase) ||
                                    f.Name.Contains("Protector", StringComparison.OrdinalIgnoreCase) ||
                                    f.Name.Contains("Accessory", StringComparison.OrdinalIgnoreCase) ||
                                    f.Name.Contains("Goods", StringComparison.OrdinalIgnoreCase));

                                if (isItemMsg)
                                {
                                    string engUSDir = Path.Combine(outputDir, "engUS");
                                    Directory.CreateDirectory(engUSDir);

                                    string outputPath = Path.Combine(engUSDir, "item.msgbnd.dcx");
                                    File.WriteAllBytes(outputPath, fileData);

                                    Console.WriteLine($"[RegTool] Extracted: item.msgbnd.dcx ({fileData.Length} bytes)");
                                    Console.WriteLine($"[RegTool]   Contains {bnd.Files.Count} files, {fmgFiles.Count} FMG files");
                                    Console.WriteLine($"[RegTool]   Sample FMG: {Path.GetFileName(fmgFiles[0].Name)}");

                                    extracted++;
                                    break;
                                }
                            }
                        }
                    }
                    catch
                    {
                        continue;
                    }
                }

                if (extracted == 0)
                {
                    Console.WriteLine("[RegTool WARN] Could not find item.msgbnd.dcx in Data0.bdt");
                    return 1;
                }

                Console.WriteLine($"[RegTool SUCCESS] Extracted item.msgbnd.dcx to: {outputDir}");
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool ERROR] {ex.Message}");
                return 1;
            }
        }

        static int ExecutePatch(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required argument: --input <source_regulation.bin>");
                return 1;
            }

            if (!options.TryGetValue("output", out string? outputPath) || string.IsNullOrEmpty(outputPath))
            {
                Console.Error.WriteLine("Missing required argument: --output <target_regulation.bin>");
                return 1;
            }

            if (!options.TryGetValue("defs", out string? defsDir) || string.IsNullOrEmpty(defsDir))
            {
                Console.Error.WriteLine("Missing required argument: --defs <paramdex_er_defs_folder>");
                return 1;
            }

            if (!options.TryGetValue("spec", out string? specPath) || string.IsNullOrEmpty(specPath))
            {
                Console.Error.WriteLine("Missing required argument: --spec <patch_spec.json>");
                return 1;
            }

            if (!File.Exists(inputPath))
            {
                Console.Error.WriteLine($"Source regulation file not found: {inputPath}");
                return 1;
            }

            if (!Directory.Exists(defsDir))
            {
                Console.Error.WriteLine($"Paramdex Defs directory not found: {defsDir}");
                return 1;
            }

            if (!File.Exists(specPath))
            {
                Console.Error.WriteLine($"Patch spec JSON file not found: {specPath}");
                return 1;
            }

            Console.WriteLine($"[RegTool] Loading patch specification: {specPath}...");
            string specJson = File.ReadAllText(specPath);
            using var doc = JsonDocument.Parse(specJson);
            var root = doc.RootElement;

            Console.WriteLine($"[RegTool] Decrypting source regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            var paramdefCache = new Dictionary<string, PARAMDEF>(StringComparer.OrdinalIgnoreCase);
            var paramCache = new Dictionary<string, (PARAM Param, BinderFile File)>(StringComparer.OrdinalIgnoreCase);

            PARAMDEF GetParamdef(string defName)
            {
                if (!paramdefCache.TryGetValue(defName, out var def))
                {
                    string xmlFile = Path.Combine(defsDir, $"{defName}.xml");
                    if (!File.Exists(xmlFile))
                    {
                        throw new FileNotFoundException($"Paramdef XML not found: {xmlFile}");
                    }
                    def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                    paramdefCache[defName] = def;
                }
                return def;
            }

            (PARAM Param, BinderFile File) GetOrLoadParam(string tableName, string defName)
            {
                if (!paramCache.TryGetValue(tableName, out var entry))
                {
                    var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                    if (file == null)
                    {
                        throw new KeyNotFoundException($"Param file '{tableName}.param' not found in regulation BND!");
                    }
                    var param = PARAM.Read(file.Bytes);
                    var def = GetParamdef(defName);
                    param.ApplyParamdefSomewhatCarefully(def);
                    entry = (param, file);
                    paramCache[tableName] = entry;
                }
                return entry;
            }

            int injectedEquipCount = 0;
            int injectedLootCount = 0;
            int injectedFmgCount = 0;

            // Collect FMG text entries from all specs for batch injection
            var allFmgTexts = new List<(int ItemId, int VanillaSourceId, bool IsWeapon, string Name, string Caption, string Info)>();

            List<JsonElement> specs = new List<JsonElement>();
            if (root.ValueKind == JsonValueKind.Array)
            {
                foreach (var el in root.EnumerateArray())
                    specs.Add(el);
            }
            else
            {
                specs.Add(root);
            }

            foreach (var setSpec in specs)
            {
                string setId = setSpec.TryGetProperty("set_id", out var sid) ? sid.GetString() ?? "unknown" : "unknown";

                // 1. Equip Params (EquipParamProtector / EquipParamWeapon)
                if (setSpec.TryGetProperty("equip_params", out var equipParamsEl) && equipParamsEl.ValueKind == JsonValueKind.Array)
                {
                    foreach (var ep in equipParamsEl.EnumerateArray())
                    {
                        string tableName = ep.GetProperty("param_table").GetString()!;
                        int newParamId = ep.GetProperty("new_param_id").GetInt32();
                        int baseCloneId = ep.TryGetProperty("base_clone_id", out var bc) ? bc.GetInt32() : 0;
                        string rowName = ep.TryGetProperty("row_name", out var rn) ? rn.GetString() ?? "" : "";

                        string defName = tableName;
                        var (param, _) = GetOrLoadParam(tableName, defName);

                        // If already present (re-forge), remove old injected row to update cleanly
                        var existingIndex = param.Rows.FindIndex(r => r.ID == newParamId);
                        if (existingIndex >= 0)
                        {
                            param.Rows.RemoveAt(existingIndex);
                        }

                        // Locate clone source row
                        PARAM.Row? baseRow = null;
                        if (baseCloneId > 0)
                        {
                            baseRow = param.Rows.FirstOrDefault(r => r.ID == baseCloneId);
                        }
                        if (baseRow == null)
                        {
                            baseRow = param.Rows.FirstOrDefault();
                        }

                        if (baseRow == null)
                        {
                            Console.WriteLine($"[RegTool WARN] Cannot find base row to clone for {tableName} ID {newParamId}");
                            continue;
                        }

                        var newRow = new PARAM.Row(baseRow)
                        {
                            ID = newParamId,
                            Name = rowName
                        };

                        if (ep.TryGetProperty("field_updates", out var fieldsEl) && fieldsEl.ValueKind == JsonValueKind.Object)
                        {
                            foreach (var prop in fieldsEl.EnumerateObject())
                            {
                                string fieldName = prop.Name;
                                if (fieldName.EndsWith("ModelId", StringComparison.OrdinalIgnoreCase))
                                {
                                    fieldName = "equipModelId";
                                }

                                var cell = newRow.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
                                if (cell != null)
                                {
                                    SetCellValue(cell, prop.Value);
                                }
                            }
                        }

                        param.Rows.Add(newRow);
                        injectedEquipCount++;
                    }
                }

                // 2. Loot Distribution (NON-DESTRUCTIVE: Never clears vanilla loot)
                if (setSpec.TryGetProperty("loot_distribution", out var lootEl) && lootEl.ValueKind == JsonValueKind.Object)
                {
                    string lootType = lootEl.TryGetProperty("type", out var lt) ? lt.GetString() ?? "" : "";
                    var awardedItems = new List<int>();
                    if (lootEl.TryGetProperty("awarded_items", out var itemsEl) && itemsEl.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var itm in itemsEl.EnumerateArray())
                            awardedItems.Add(itm.GetInt32());
                    }

                    if (lootType == "enemy_drop" && awardedItems.Count > 0)
                    {
                        int targetLotId = 0;
                        if (lootEl.TryGetProperty("target_id", out var tid) && int.TryParse(tid.GetString(), out int parsedTid) && parsedTid > 0)
                        {
                            targetLotId = parsedTid;
                        }
                        else if (lootEl.TryGetProperty("lot_id", out var lid) && lid.GetInt32() > 0)
                        {
                            targetLotId = lid.GetInt32();
                        }

                        string targetEnemy = lootEl.TryGetProperty("target_enemy", out var te) ? te.GetString() ?? "Wild Enemy" : "Wild Enemy";
                        double dropRatePercent = lootEl.TryGetProperty("drop_rate_percent", out var dr) ? dr.GetDouble() : 20.0;

                        if (targetLotId > 0)
                        {
                            var (itemLotParam, _) = GetOrLoadParam("ItemLotParam_enemy", "ItemLotParam");

                            var targetLotRow = itemLotParam.Rows.FirstOrDefault(r => r.ID == targetLotId);

                            if (targetLotRow == null)
                            {
                                // New standalone lot row: clone from template
                                var baseLot = itemLotParam.Rows.FirstOrDefault();
                                if (baseLot != null)
                                {
                                    targetLotRow = new PARAM.Row(baseLot)
                                    {
                                        ID = targetLotId,
                                        Name = $"[LootForge] {targetEnemy}"
                                    };
                                    // For a new standalone row, initialize slots to empty
                                    for (int slot = 1; slot <= 8; slot++)
                                    {
                                        SetCellIfExists(targetLotRow, $"lotItemId0{slot}", 0);
                                        SetCellIfExists(targetLotRow, $"lotItemCategory0{slot}", 0);
                                        SetCellIfExists(targetLotRow, $"lotItemBasePoint0{slot}", (ushort)0);
                                        SetCellIfExists(targetLotRow, $"lotItemNum0{slot}", (byte)0);
                                    }
                                    itemLotParam.Rows.Add(targetLotRow);
                                }
                            }

                            if (targetLotRow != null)
                            {
                                ushort ratePoints = (ushort)Math.Clamp((int)(dropRatePercent * 100), 1, 10000);

                                // IMPORTANT: DO NOT CLEAR VANILLA LOOT!
                                // Append custom mod items into empty slots (lotItemId == 0) or update existing slot with same itemId.
                                int itemIndex = 0;
                                while (itemIndex < awardedItems.Count)
                                {
                                    int itemId = awardedItems[itemIndex];
                                    bool isWeapon = itemId < 5000000;

                                    int existingSlot = -1;
                                    int firstEmptySlot = -1;

                                    for (int s = 1; s <= 8; s++)
                                    {
                                        int curItem = GetCellInt(targetLotRow, $"lotItemId0{s}");
                                        if (curItem == itemId)
                                        {
                                            existingSlot = s;
                                            break;
                                        }
                                        if (curItem == 0 && firstEmptySlot == -1)
                                        {
                                            firstEmptySlot = s;
                                        }
                                    }

                                    int slotToUse = existingSlot != -1 ? existingSlot : firstEmptySlot;
                                    if (slotToUse != -1)
                                    {
                                        SetCellIfExists(targetLotRow, $"lotItemId0{slotToUse}", itemId);
                                        SetCellIfExists(targetLotRow, $"lotItemCategory0{slotToUse}", isWeapon ? 0x20000000 : 0x10000000);
                                        SetCellIfExists(targetLotRow, $"lotItemBasePoint0{slotToUse}", ratePoints);
                                        SetCellIfExists(targetLotRow, $"lotItemNum0{slotToUse}", (byte)1);
                                    }
                                    else
                                    {
                                        // All 8 slots in this row are occupied by vanilla drops!
                                        // Create a secondary chained lot row rather than overwriting vanilla drops!
                                        int overflowLotId = targetLotId < 9000000 ? 9100000 + (targetLotId % 10000) : targetLotId + 1;
                                        var overflowRow = itemLotParam.Rows.FirstOrDefault(r => r.ID == overflowLotId);
                                        if (overflowRow == null)
                                        {
                                            var baseLot = itemLotParam.Rows.FirstOrDefault();
                                            if (baseLot != null)
                                            {
                                                overflowRow = new PARAM.Row(baseLot)
                                                {
                                                    ID = overflowLotId,
                                                    Name = $"[LootForge Chained] {targetEnemy}"
                                                };
                                                for (int s = 1; s <= 8; s++)
                                                {
                                                    SetCellIfExists(overflowRow, $"lotItemId0{s}", 0);
                                                    SetCellIfExists(overflowRow, $"lotItemCategory0{s}", 0);
                                                    SetCellIfExists(overflowRow, $"lotItemBasePoint0{s}", (ushort)0);
                                                    SetCellIfExists(overflowRow, $"lotItemNum0{s}", (byte)0);
                                                }
                                                itemLotParam.Rows.Add(overflowRow);
                                            }
                                        }
                                        if (overflowRow != null)
                                        {
                                            SetCellIfExists(overflowRow, "lotItemId01", itemId);
                                            SetCellIfExists(overflowRow, "lotItemCategory01", isWeapon ? 0x20000000 : 0x10000000);
                                            SetCellIfExists(overflowRow, "lotItemBasePoint01", ratePoints);
                                            SetCellIfExists(overflowRow, "lotItemNum01", (byte)1);
                                        }
                                    }

                                    itemIndex++;
                                }
                                injectedLootCount++;
                            }
                        }
                    }
                    else if ((lootType == "shop_lineup" || lootType == "merchant_shop") && awardedItems.Count > 0)
                    {
                        var (shopParam, _) = GetOrLoadParam("ShopLineupParam", "ShopLineupParam");
                        string shopName = lootEl.TryGetProperty("display_name", out var dn) ? dn.GetString() ?? "Merchant" : "Merchant";
                        if (string.IsNullOrEmpty(shopName) && lootEl.TryGetProperty("merchant_name", out var mn))
                            shopName = mn.GetString() ?? "Merchant";

                        int cost = 500;
                        if (lootEl.TryGetProperty("cost_or_remembrance", out var cst))
                            cost = (int)cst.GetDouble();
                        else if (lootEl.TryGetProperty("rune_cost", out var rc))
                            cost = rc.GetInt32();

                        string targetId = "";
                        if (lootEl.TryGetProperty("target_id", out var tid))
                            targetId = tid.GetString() ?? "";
                        else if (lootEl.TryGetProperty("shop_id", out var sIdEl))
                            targetId = sIdEl.GetString() ?? "";

                        // Determine the merchant's active shop ID range in Elden Ring
                        int rangeStart = 100500;
                        int rangeEnd = 100524;

                        if (targetId.Contains("kale", StringComparison.OrdinalIgnoreCase) ||
                            shopName.Contains("kale", StringComparison.OrdinalIgnoreCase) ||
                            shopName.Contains("kalé", StringComparison.OrdinalIgnoreCase))
                        {
                            // Merchant Kalé at Church of Elleh
                            rangeStart = 100500;
                            rangeEnd = 100524;
                        }
                        else if (targetId.Contains("twin", StringComparison.OrdinalIgnoreCase) ||
                                 targetId.Contains("maiden", StringComparison.OrdinalIgnoreCase) ||
                                 targetId.Contains("husks", StringComparison.OrdinalIgnoreCase) ||
                                 shopName.Contains("twin", StringComparison.OrdinalIgnoreCase) ||
                                 shopName.Contains("husks", StringComparison.OrdinalIgnoreCase))
                        {
                            // Twin Maiden Husks at Roundtable Hold
                            rangeStart = 101800;
                            rangeEnd = 101899;
                        }
                        else if (targetId.Contains("liurnia", StringComparison.OrdinalIgnoreCase) ||
                                 shopName.Contains("liurnia", StringComparison.OrdinalIgnoreCase))
                        {
                            // Nomadic Merchant at Liurnia Lake Shore
                            rangeStart = 100625;
                            rangeEnd = 100637;
                        }
                        else if (lootType == "shop_lineup" ||
                                 targetId.Contains("remembrance", StringComparison.OrdinalIgnoreCase) ||
                                 shopName.Contains("remembrance", StringComparison.OrdinalIgnoreCase) ||
                                 shopName.Contains("enia", StringComparison.OrdinalIgnoreCase))
                        {
                            // Finger Reader Enia Boss Remembrances
                            rangeStart = 101900;
                            rangeEnd = 101949;
                        }
                        else
                        {
                            // Dynamic search for any other merchant in shopParam rows
                            var matchingRows = shopParam.Rows.Where(r =>
                                r.Name != null && (r.Name.Contains(shopName, StringComparison.OrdinalIgnoreCase) ||
                                                   (!string.IsNullOrEmpty(targetId) && r.Name.Contains(targetId, StringComparison.OrdinalIgnoreCase)))).ToList();
                            if (matchingRows.Count > 0)
                            {
                                rangeStart = matchingRows.Min(r => r.ID);
                                rangeEnd = matchingRows.Max(r => r.ID);
                            }
                        }

                        // Pick template row from this merchant so all default flags match perfectly
                        var templateRow = shopParam.Rows.FirstOrDefault(r => r.ID >= rangeStart && r.ID <= rangeEnd)
                                          ?? shopParam.Rows.FirstOrDefault();

                        for (int i = 0; i < awardedItems.Count; i++)
                        {
                            int itemId = awardedItems[i];

                            // Check if this item is already in this merchant's shop
                            var existingRow = shopParam.Rows.FirstOrDefault(r =>
                                r.ID >= rangeStart && r.ID <= rangeEnd && GetCellInt(r, "equipId") == itemId);

                            PARAM.Row targetShopRow;
                            if (existingRow != null)
                            {
                                targetShopRow = existingRow;
                            }
                            else
                            {
                                // Find first unused ID in this merchant's range
                                int shopRowId = -1;
                                for (int cand = rangeStart; cand <= rangeEnd; cand++)
                                {
                                    if (!shopParam.Rows.Any(r => r.ID == cand))
                                    {
                                        shopRowId = cand;
                                        break;
                                    }
                                }

                                if (shopRowId == -1)
                                {
                                    // If range is tightly packed, extend beyond rangeEnd
                                    shopRowId = rangeEnd + 1;
                                    while (shopParam.Rows.Any(r => r.ID == shopRowId))
                                        shopRowId++;
                                }

                                targetShopRow = new PARAM.Row(templateRow!)
                                {
                                    ID = shopRowId,
                                    Name = $"[LootForge] {shopName}"
                                };
                                shopParam.Rows.Add(targetShopRow);
                            }

                            bool isWeapon = itemId < 5000000;
                            SetCellIfExists(targetShopRow, "equipId", itemId);
                            SetCellIfExists(targetShopRow, "equipType", (byte)(isWeapon ? 0 : 1)); // 0 = Weapon, 1 = Protector/Armor
                            SetCellIfExists(targetShopRow, "value", cost);
                            SetCellIfExists(targetShopRow, "mtrlId", -1);
                            SetCellIfExists(targetShopRow, "eventFlag_forRelease", 0u);
                            SetCellIfExists(targetShopRow, "eventFlag_forStock", 0u);
                            SetCellIfExists(targetShopRow, "sellQuantity", (short)-1);
                            SetCellIfExists(targetShopRow, "costType", (byte)0);
                            SetCellIfExists(targetShopRow, "setNum", (ushort)1);
                            SetCellIfExists(targetShopRow, "value_Add", 0);
                            SetCellIfExists(targetShopRow, "value_Magnification", 1.0f);
                            SetCellIfExists(targetShopRow, "iconId", -1);
                            SetCellIfExists(targetShopRow, "nameMsgId", -1);
                            SetCellIfExists(targetShopRow, "menuTitleMsgId", -1);
                            SetCellIfExists(targetShopRow, "menuIconId", (short)-1);

                            injectedLootCount++;
                        }
                    }
                }

                // 3. Collect FMG text entries for batch injection
                if (setSpec.TryGetProperty("fmg_texts", out var fmgTextsEl) && fmgTextsEl.ValueKind == JsonValueKind.Array)
                {
                    foreach (var ft in fmgTextsEl.EnumerateArray())
                    {
                        int ftItemId = ft.GetProperty("item_id").GetInt32();
                        int ftVanillaId = ft.TryGetProperty("vanilla_source_id", out var vs) ? vs.GetInt32() : 0;
                        bool ftIsWeapon = ft.TryGetProperty("is_weapon", out var iw) && iw.GetBoolean();
                        string ftName = ft.TryGetProperty("name", out var n) ? n.GetString() ?? "" : "";
                        string ftCaption = ft.TryGetProperty("caption", out var c) ? c.GetString() ?? "" : "";
                        string ftInfo = ft.TryGetProperty("info", out var inf) ? inf.GetString() ?? "" : "";
                        allFmgTexts.Add((ftItemId, ftVanillaId, ftIsWeapon, ftName, ftCaption, ftInfo));
                    }
                }
            }

            foreach (var kvp in paramCache)
            {
                var (param, file) = kvp.Value;
                Console.WriteLine($"[RegTool] Serializing modified table: {kvp.Key} ({param.Rows.Count} rows)...");
                file.Bytes = param.Write();
            }

            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
            {
                Directory.CreateDirectory(outDir);
            }

            Console.WriteLine($"[RegTool] Encrypting and saving modified regulation to: {outputPath}...");
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);

            // ─── Phase 2: FMG Text Injection ───────────────────────────────────
            if (options.TryGetValue("msg", out string? msgDir) && !string.IsNullOrEmpty(msgDir) && allFmgTexts.Count > 0)
            {
                injectedFmgCount = InjectFmgTexts(msgDir, outputPath, allFmgTexts);
            }
            else if (allFmgTexts.Count > 0)
            {
                Console.WriteLine($"[RegTool WARN] No --msg directory provided. Skipping FMG text injection for {allFmgTexts.Count} item(s).");
                Console.WriteLine("     Items will display as ?ProtectorName? / ?WeaponName? in-game.");
            }

            Console.WriteLine($"[RegTool SUCCESS] Successfully patched regulation.bin!");
            Console.WriteLine($" - Injected equipment entries: {injectedEquipCount}");
            Console.WriteLine($" - Injected loot/shop entries: {injectedLootCount}");
            Console.WriteLine($" - Injected FMG text entries:  {injectedFmgCount}");
            Console.WriteLine($" - Output file size: {new FileInfo(outputPath).Length} bytes");
            return 0;
        }

        /// <summary>
        /// Injects FMG text entries (item names, descriptions, captions) into item.msgbnd.dcx.
        /// Copies authentic vanilla text from the source item being replaced and annotates
        /// with the LootForge marker. Falls back to provided strings if vanilla lookup fails.
        /// </summary>
        static int InjectFmgTexts(
            string msgDir,
            string regulationOutputPath,
            List<(int ItemId, int VanillaSourceId, bool IsWeapon, string Name, string Caption, string Info)> fmgTexts)
        {
            string itemMsgBndPath = Path.Combine(msgDir, "item.msgbnd.dcx");
            if (!File.Exists(itemMsgBndPath))
            {
                Console.WriteLine($"[RegTool WARN] item.msgbnd.dcx not found at: {itemMsgBndPath}. Skipping FMG injection.");
                return 0;
            }

            // Create .bak file before modifying
            string bakPath = itemMsgBndPath + ".bak";
            if (!File.Exists(bakPath))
            {
                File.Copy(itemMsgBndPath, bakPath, false);
                Console.WriteLine($"[RegTool] Created backup: {bakPath}");
            }

            Console.WriteLine($"[RegTool] Loading item.msgbnd.dcx from: {itemMsgBndPath}...");
            BND4 msgBnd = BND4.Read(itemMsgBndPath);

            // Locate FMG files by their internal path name (exclude _dlc variants)
            var fmgFileCache = new Dictionary<string, (FMG Fmg, BinderFile File)>(StringComparer.OrdinalIgnoreCase);

            FMG? FindAndLoadFmg(string categoryName)
            {
                if (fmgFileCache.TryGetValue(categoryName, out var cached))
                    return cached.Fmg;

                // Match exact file name e.g. "ProtectorName.fmg" at end of the internal path
                var binderFile = msgBnd.Files.FirstOrDefault(f =>
                    f.Name != null &&
                    Path.GetFileName(f.Name).Equals($"{categoryName}.fmg", StringComparison.OrdinalIgnoreCase));

                if (binderFile == null)
                {
                    Console.WriteLine($"[RegTool WARN] FMG file '{categoryName}.fmg' not found in item.msgbnd.dcx");
                    return null;
                }

                var fmg = FMG.Read(binderFile.Bytes);
                fmgFileCache[categoryName] = (fmg, binderFile);
                return fmg;
            }

            // Pre-load all relevant FMG categories
            var protectorName    = FindAndLoadFmg("ProtectorName");
            var protectorInfo    = FindAndLoadFmg("ProtectorInfo");
            var protectorCaption = FindAndLoadFmg("ProtectorCaption");
            var weaponName       = FindAndLoadFmg("WeaponName");
            var weaponInfo       = FindAndLoadFmg("WeaponInfo");
            var weaponCaption    = FindAndLoadFmg("WeaponCaption");

            int count = 0;

            foreach (var (itemId, vanillaSourceId, isWeapon, fallbackName, fallbackCaption, fallbackInfo) in fmgTexts)
            {
                FMG? nameFmg    = isWeapon ? weaponName    : protectorName;
                FMG? infoFmg    = isWeapon ? weaponInfo    : protectorInfo;
                FMG? captionFmg = isWeapon ? weaponCaption : protectorCaption;

                if (nameFmg == null) continue;

                // Look up vanilla source text for authentic names/descriptions
                string nameText = fallbackName;
                string infoText = fallbackInfo;
                string captionText = fallbackCaption;

                if (vanillaSourceId > 0)
                {
                    var vanillaNameEntry = nameFmg.Entries.FirstOrDefault(e => e.ID == vanillaSourceId);
                    if (vanillaNameEntry?.Text != null && vanillaNameEntry.Text.Length > 0)
                    {
                        nameText = $"\u2726 [LootForge] {vanillaNameEntry.Text}";
                    }

                    if (infoFmg != null)
                    {
                        var vanillaInfoEntry = infoFmg.Entries.FirstOrDefault(e => e.ID == vanillaSourceId);
                        if (vanillaInfoEntry?.Text != null && vanillaInfoEntry.Text.Length > 0)
                            infoText = vanillaInfoEntry.Text;
                    }

                    if (captionFmg != null)
                    {
                        var vanillaCaptionEntry = captionFmg.Entries.FirstOrDefault(e => e.ID == vanillaSourceId);
                        if (vanillaCaptionEntry?.Text != null && vanillaCaptionEntry.Text.Length > 0)
                            captionText = vanillaCaptionEntry.Text;
                    }
                }

                // Remove existing entries if re-forging (idempotent)
                nameFmg.Entries.RemoveAll(e => e.ID == itemId);
                nameFmg.Entries.Add(new FMG.Entry(itemId, nameText));

                if (infoFmg != null)
                {
                    infoFmg.Entries.RemoveAll(e => e.ID == itemId);
                    infoFmg.Entries.Add(new FMG.Entry(itemId, infoText));
                }

                if (captionFmg != null)
                {
                    captionFmg.Entries.RemoveAll(e => e.ID == itemId);
                    captionFmg.Entries.Add(new FMG.Entry(itemId, captionText));
                }

                count++;
            }

            // Write modified FMGs back into the BND
            foreach (var kvp in fmgFileCache)
            {
                kvp.Value.File.Bytes = kvp.Value.Fmg.Write();
            }

            // Save to mod output directory alongside regulation.bin
            string outputMsgDir = Path.Combine(Path.GetDirectoryName(regulationOutputPath)!, "msg", "engUS");
            Directory.CreateDirectory(outputMsgDir);
            string outputMsgBndPath = Path.Combine(outputMsgDir, "item.msgbnd.dcx");
            msgBnd.Write(outputMsgBndPath);

            Console.WriteLine($"[RegTool] Injected {count} FMG text entries. Saved to: {outputMsgBndPath}");
            return count;
        }

        static int GetCellInt(PARAM.Row row, string fieldName)
        {
            var cell = row.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
            if (cell == null || cell.Value == null) return 0;
            try
            {
                return Convert.ToInt32(cell.Value);
            }
            catch
            {
                return 0;
            }
        }

        static void SetCellIfExists(PARAM.Row row, string fieldName, object value)
        {
            var cell = row.Cells.FirstOrDefault(c => string.Equals(c.Def.InternalName, fieldName, StringComparison.OrdinalIgnoreCase));
            if (cell != null)
            {
                cell.Value = value;
            }
        }

        static void SetCellValue(PARAM.Cell cell, JsonElement jsonVal)
        {
            switch (cell.Def.DisplayType)
            {
                case PARAMDEF.DefType.s8:
                    cell.Value = (sbyte)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.u8:
                    cell.Value = (byte)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.s16:
                    cell.Value = (short)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.u16:
                    cell.Value = (ushort)jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.s32:
                case PARAMDEF.DefType.b32:
                    cell.Value = jsonVal.GetInt32();
                    break;
                case PARAMDEF.DefType.u32:
                    cell.Value = (uint)jsonVal.GetInt64();
                    break;
                case PARAMDEF.DefType.f32:
                    cell.Value = (float)jsonVal.GetDouble();
                    break;
                case PARAMDEF.DefType.f64:
                    cell.Value = jsonVal.GetDouble();
                    break;
                case PARAMDEF.DefType.fixstr:
                case PARAMDEF.DefType.fixstrW:
                    cell.Value = jsonVal.GetString() ?? "";
                    break;
                default:
                    break;
            }
        }
    }
}
