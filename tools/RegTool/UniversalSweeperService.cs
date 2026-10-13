using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service that sweeps and infuses ALL valid vanilla items in EquipParamWeapon,
    /// EquipParamProtector, and EquipParamAccessory with Diablo ARPG stats, affixes,
    /// and weapon skills.
    /// Ensures that pure unmodded vanilla items NO LONGER EXIST in the world.
    /// Fully schema-driven and compatible with any overhaul mod. Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class UniversalSweeperService
    {
        public enum DiabloRarity
        {
            Magic = 1,
            Rare = 2,
            Legendary = 3,
            Mythic = 4
        }

        private static readonly int[] AUTHENTIC_SKILLS = new[]
        {
            200, 201, 202, 203, 204, 205, 206, 208, 209, 210,
            215, 216, 217, 218, 220, 221, 222, 223, 225, 227,
            230, 231, 233, 234, 235, 236, 237, 238
        };

        public static int ExecuteSweep(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("[UniversalSweeper] Missing required --input path to regulation.bin.");
                return 1;
            }
            string outputPath = options.TryGetValue("output", out string? op) && !string.IsNullOrEmpty(op) ? op : inputPath;
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            string? msgDir = options.TryGetValue("msg", out string? md) ? md : null;
            bool randomizeSkills = !options.TryGetValue("randomize-skills", out string? rs) || !bool.TryParse(rs, out bool parsedRs) || parsedRs;
            int seed = options.TryGetValue("seed", out string? sdStr) && int.TryParse(sdStr, out int parsedSeed) ? parsedSeed : 42;

            var rng = new Random(seed);

            Console.WriteLine($"[UniversalSweeper] Loading and decrypting: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            PARAM LoadParam(string tableName)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file == null) throw new Exception($"Table {tableName} not found in regulation.");
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

            var wepParam = LoadParam("EquipParamWeapon");
            var protParam = LoadParam("EquipParamProtector");
            var accParam = LoadParam("EquipParamAccessory");

            // FMG BND loading for live name and description mutation
            BND4? itemMsgBnd = null;
            BND4? dlcMsgBnd = null;
            string? itemMsgPath = null;
            string? dlcMsgPath = null;

            if (!string.IsNullOrEmpty(msgDir) && Directory.Exists(msgDir))
            {
                itemMsgPath = Path.Combine(msgDir, "item.msgbnd.dcx");
                dlcMsgPath = Path.Combine(msgDir, "item_dlc02.msgbnd.dcx");
                if (File.Exists(itemMsgPath))
                {
                    try
                    {
                        itemMsgBnd = BND4.Read(itemMsgPath);
                        if (File.Exists(dlcMsgPath))
                            dlcMsgBnd = BND4.Read(dlcMsgPath);
                        Console.WriteLine("[UniversalSweeper] Loaded FMG message packages for in-place text infusion.");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[UniversalSweeper WARN] Could not load FMG message packages: {ex.Message}");
                    }
                }
            }

            // Dictionaries for fast FMG lookups
            var fmgCache = new Dictionary<string, FMG>(StringComparer.OrdinalIgnoreCase);
            FMG? GetFmg(string category)
            {
                if (itemMsgBnd == null) return null;
                if (fmgCache.TryGetValue(category, out var cached)) return cached;

                var f = itemMsgBnd.Files.FirstOrDefault(bf => bf.Name.EndsWith($"{category}.fmg", StringComparison.OrdinalIgnoreCase));
                if (f != null)
                {
                    var fmg = FMG.Read(f.Bytes);
                    fmgCache[category] = fmg;
                    return fmg;
                }
                return null;
            }

            var wepNameFmg = GetFmg("WeaponName");
            var wepCaptionFmg = GetFmg("WeaponCaption");
            var protNameFmg = GetFmg("ProtectorName");
            var protCaptionFmg = GetFmg("ProtectorCaption");
            var accNameFmg = GetFmg("AccessoryName");
            var accCaptionFmg = GetFmg("AccessoryCaption");

            DiabloRarity RollRarity()
            {
                int r = rng.Next(100);
                if (r < 40) return DiabloRarity.Magic;       // 40%
                if (r < 75) return DiabloRarity.Rare;        // 35%
                if (r < 95) return DiabloRarity.Legendary;   // 20%
                return DiabloRarity.Mythic;                  // 5%
            }

            // 1. Group valid player weapons by base family ID
            var weaponFamilies = new Dictionary<int, List<PARAM.Row>>();
            int totalEligibleWeapons = 0;

            foreach (var r in wepParam.Rows)
            {
                int wepType = ParamHelper.GetCellInt(r, "wepType");
                int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");
                int sortId = ParamHelper.GetCellInt(r, "sortId");
                int modelId = ParamHelper.GetCellInt(r, "equipModelId");
                int originId = ParamHelper.GetCellInt(r, "originEquipWep");

                if (wepType > 0 && isDeposit == 1 && sortId > 0 && modelId > 0)
                {
                    totalEligibleWeapons++;
                    int familyId = originId > 0 ? originId : (r.ID - (r.ID % 100));
                    if (!weaponFamilies.TryGetValue(familyId, out var famList))
                    {
                        famList = new List<PARAM.Row>();
                        weaponFamilies[familyId] = famList;
                    }
                    famList.Add(r);
                }
            }

            Console.WriteLine($"[UniversalSweeper] Infusing {totalEligibleWeapons} weapon rows across {weaponFamilies.Count} weapon archetypes...");

            int infusedWeapons = 0;
            foreach (var kvp in weaponFamilies)
            {
                int familyId = kvp.Key;
                var members = kvp.Value;

                var rarity = RollRarity();
                float dmgMult = 1.0f + ((int)rarity * 0.10f); // +10%, +20%, +30%, +40%
                float scalingAdd = (int)rarity * 5f;

                int? chosenSkill = null;
                if (randomizeSkills)
                {
                    chosenSkill = AUTHENTIC_SKILLS[rng.Next(AUTHENTIC_SKILLS.Length)];
                }

                // Mutate every row in the weapon family (base + upgrade levels + affinities)
                foreach (var row in members)
                {
                    int basePhys = ParamHelper.GetCellInt(row, "attackBasePhysics");
                    if (basePhys > 0)
                    {
                        ParamHelper.SetCellIfExists(row, "attackBasePhysics", (ushort)Math.Clamp((int)Math.Round(basePhys * dmgMult), 1, 65535));
                    }

                    int strScale = ParamHelper.GetCellInt(row, "correctStrength");
                    if (strScale > 0)
                        ParamHelper.SetCellIfExists(row, "correctStrength", (float)(strScale + scalingAdd));

                    int dexScale = ParamHelper.GetCellInt(row, "correctAgility");
                    if (dexScale > 0)
                        ParamHelper.SetCellIfExists(row, "correctAgility", (float)(dexScale + scalingAdd));

                    if (chosenSkill.HasValue)
                    {
                        ParamHelper.SetCellIfExists(row, "swordArtsParamId", chosenSkill.Value);
                    }

                    // FMG mutation
                    if (wepNameFmg != null)
                    {
                        var entry = wepNameFmg.Entries.FirstOrDefault(e => e.ID == row.ID);
                        if (entry != null && !string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.StartsWith("["))
                        {
                            entry.Text = $"[{rarity.ToString().ToUpper()}] {entry.Text.Trim()}";
                        }
                    }

                    if (wepCaptionFmg != null)
                    {
                        var entry = wepCaptionFmg.Entries.FirstOrDefault(e => e.ID == row.ID);
                        if (entry != null && !string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.Contains("[Diablo"))
                        {
                            entry.Text = $"[Diablo {rarity}] +{(int)((dmgMult - 1f) * 100)}% Attack Power, +{(int)scalingAdd} Scaling\n{entry.Text.Trim()}";
                        }
                    }

                    infusedWeapons++;
                }
            }

            // 2. Infuse ALL valid player protectors
            int infusedProtectors = 0;
            foreach (var r in protParam.Rows)
            {
                int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");
                int sortId = ParamHelper.GetCellInt(r, "sortId");
                int modelId = ParamHelper.GetCellInt(r, "equipModelId");

                if (isDeposit == 1 && sortId > 0 && modelId > 0)
                {
                    var rarity = RollRarity();
                    float defMult = 1.0f + ((int)rarity * 0.08f); // +8%, +16%, +24%, +32%
                    short poiseAdd = (short)((int)rarity * 3);

                    string[] defFields = { "defensePhysics", "defenseMagic", "defenseFire", "defenseThunder", "defenseSlash", "defenseBlow", "defenseThrust" };
                    foreach (var f in defFields)
                    {
                        int cur = ParamHelper.GetCellInt(r, f);
                        if (cur > 0)
                        {
                            ParamHelper.SetCellIfExists(r, f, (ushort)Math.Clamp((int)Math.Round(cur * defMult), 1, 65535));
                        }
                    }

                    int poise = ParamHelper.GetCellInt(r, "saDurability");
                    if (poise > 0)
                    {
                        ParamHelper.SetCellIfExists(r, "saDurability", (short)(poise + poiseAdd));
                    }

                    // FMG mutation
                    if (protNameFmg != null)
                    {
                        var entry = protNameFmg.Entries.FirstOrDefault(e => e.ID == r.ID);
                        if (entry != null && !string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.StartsWith("["))
                        {
                            entry.Text = $"[{rarity.ToString().ToUpper()}] {entry.Text.Trim()}";
                        }
                    }

                    if (protCaptionFmg != null)
                    {
                        var entry = protCaptionFmg.Entries.FirstOrDefault(e => e.ID == r.ID);
                        if (entry != null && !string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.Contains("[Diablo"))
                        {
                            entry.Text = $"[Diablo {rarity}] +{(int)((defMult - 1f) * 100)}% Defenses, +{poiseAdd} Poise\n{entry.Text.Trim()}";
                        }
                    }

                    infusedProtectors++;
                }
            }

            // 3. Infuse ALL valid player accessories (talismans)
            int infusedAccessories = 0;
            foreach (var r in accParam.Rows)
            {
                int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");
                int sortId = ParamHelper.GetCellInt(r, "sortId");

                if (isDeposit == 1 && sortId > 0)
                {
                    var rarity = RollRarity();
                    if (accNameFmg != null)
                    {
                        var entry = accNameFmg.Entries.FirstOrDefault(e => e.ID == r.ID);
                        if (entry != null && !string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.StartsWith("["))
                        {
                            entry.Text = $"[{rarity.ToString().ToUpper()}] {entry.Text.Trim()}";
                        }
                    }
                    if (accCaptionFmg != null)
                    {
                        var entry = accCaptionFmg.Entries.FirstOrDefault(e => e.ID == r.ID);
                        if (entry != null && !string.IsNullOrWhiteSpace(entry.Text) && !entry.Text.Contains("[Diablo"))
                        {
                            entry.Text = $"[Diablo {rarity}] Sacred Relic\n{entry.Text.Trim()}";
                        }
                    }
                    infusedAccessories++;
                }
            }

            Console.WriteLine($"[UniversalSweeper SUCCESS] Infused {infusedWeapons} weapons, {infusedProtectors} protectors, {infusedAccessories} accessories.");

            // Repack params into regulation BND4
            void SaveParamBytes(string tableName, PARAM param)
            {
                var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                if (file != null) file.Bytes = param.Write();
            }

            SaveParamBytes("EquipParamWeapon", wepParam);
            SaveParamBytes("EquipParamProtector", protParam);
            SaveParamBytes("EquipParamAccessory", accParam);

            // Re-encrypt regulation
            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir)) Directory.CreateDirectory(outDir);
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);
            Console.WriteLine($"[UniversalSweeper] Encrypted updated regulation.bin to: {outputPath}");

            // Save repacked FMGs if modified
            if (itemMsgBnd != null && !string.IsNullOrEmpty(itemMsgPath))
            {
                foreach (var kvp in fmgCache)
                {
                    string cat = kvp.Key;
                    var fmg = kvp.Value;
                    var bf = itemMsgBnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{cat}.fmg", StringComparison.OrdinalIgnoreCase));
                    if (bf != null) bf.Bytes = fmg.Write();

                    if (dlcMsgBnd != null)
                    {
                        var dlcBf = dlcMsgBnd.Files.FirstOrDefault(f => f.Name.EndsWith($"{cat}.fmg", StringComparison.OrdinalIgnoreCase));
                        if (dlcBf != null) dlcBf.Bytes = fmg.Write();
                    }
                }
                itemMsgBnd.Write(itemMsgPath);
                Console.WriteLine($"[UniversalSweeper] Saved updated item messages to: {itemMsgPath}");
                if (dlcMsgBnd != null && !string.IsNullOrEmpty(dlcMsgPath))
                {
                    dlcMsgBnd.Write(dlcMsgPath);
                    Console.WriteLine($"[UniversalSweeper] Mirrored updated messages to DLC: {dlcMsgPath}");
                }
            }

            return 0;
        }
    }
}
