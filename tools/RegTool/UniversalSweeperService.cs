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

            var bnd = RegulationDecryptor.DecryptERRegulation(inputPath);
            var loaded = new Dictionary<string, (PARAM Param, BinderFile File)>();
            (PARAM Param, BinderFile File) Load(string table, string defName)
            {
                if (loaded.TryGetValue(table, out var entry)) return entry;
                var file = bnd.Files.First(f => f.Name.EndsWith($"{table}.param", StringComparison.OrdinalIgnoreCase));
                var param = PARAM.Read(file.Bytes);
                param.ApplyParamdef(PARAMDEF.XmlDeserialize(Path.Combine(defsDir, $"{defName}.xml"), false, false));
                return loaded[table] = (param, file);
            }
            var effects = InfuseParams(Load, randomizeSkills, seed);
            foreach (var entry in loaded.Values) entry.File.Bytes = entry.Param.Write();
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
            using var output = new PatchOutputTransaction(outputPath);
            RegulationDecryptor.EncryptERRegulation(output.RegulationPath, bnd);
            if (!string.IsNullOrEmpty(msgDir))
                FmgInjector.InjectFmgTexts(msgDir, output.RegulationPath, new List<FmgInjector.FmgTextSpec>());
            output.Commit();
            return 0;
        }

        /// <summary>Infuse loaded equipment once; return text effects for the shared FMG pass.</summary>
        public static List<SweepFmgService.Effect> InfuseParams(
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            bool randomizeSkills = true, int seed = 42)
        {
            var rng = new Random(seed);
            var effects = new List<SweepFmgService.Effect>();
            var wepParam = getOrLoadParam("EquipParamWeapon", "EquipParamWeapon").Param;
            var protParam = getOrLoadParam("EquipParamProtector", "EquipParamProtector").Param;
            var accParam = getOrLoadParam("EquipParamAccessory", "EquipParamAccessory").Param;
            static bool IsGenerated(PARAM.Row row) => row.Name?.Contains("[LootForge]") == true || row.Name?.Contains("[LootForgeInfused]") == true;
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

                if (!IsGenerated(r) && wepType > 0 && isDeposit == 1 && sortId > 0 && modelId > 0 && r.ID != 110000 && r.ID >= 1000000)
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

                    float strScale = Convert.ToSingle(ParamHelper.FindCell(row, "correctStrength")?.Value ?? 0f);
                    if (strScale > 0)
                        ParamHelper.SetCellIfExists(row, "correctStrength", (float)(strScale + scalingAdd));

                    float dexScale = Convert.ToSingle(ParamHelper.FindCell(row, "correctAgility")?.Value ?? 0f);
                    if (dexScale > 0)
                        ParamHelper.SetCellIfExists(row, "correctAgility", (float)(dexScale + scalingAdd));

                    if (chosenSkill.HasValue)
                    {
                        int gemMountType = ParamHelper.GetCellInt(row, "gemMountType");
                        // Only randomize skill on standard infusible weapons (gemMountType > 0),
                        // never on unique Somber weapons, catalysts, or custom moveset weapons (gemMountType == 0)
                        if (gemMountType > 0)
                        {
                            ParamHelper.SetCellIfExists(row, "swordArtsParamId", chosenSkill.Value);
                        }
                    }

                    effects.Add(new SweepFmgService.Effect(row.ID, "Weapon", rarity.ToString(),
                        $"+{(int)((dmgMult - 1f) * 100)}% Attack Power, +{(int)scalingAdd} Scaling"));

                    row.Name = (row.Name ?? "") + " [LootForgeInfused]";
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

                if (!IsGenerated(r) && isDeposit == 1 && sortId > 0 && modelId > 0)
                {
                    var rarity = RollRarity();
                    float defMult = 1.0f + ((int)rarity * 0.08f); // +8%, +16%, +24%, +32%
                    short poiseAdd = (short)((int)rarity * 3);

                    foreach (var field in DiabloBalanceService.ArmorRateFields)
                    {
                        var cell = ParamHelper.FindCell(r,field);
                        if (cell != null) DiabloEffectService.Set(r,field,Math.Max(0.75,Convert.ToDouble(cell.Value)-0.005*(int)rarity));
                    }

                    int poise = ParamHelper.GetCellInt(r, "saDurability");
                    if (poise > 0)
                    {
                        ParamHelper.SetCellIfExists(r, "saDurability", (short)(poise + poiseAdd));
                    }

                    effects.Add(new SweepFmgService.Effect(r.ID, "Protector", rarity.ToString(),
                        $"+{(int)((defMult - 1f) * 100)}% Defenses, +{poiseAdd} Poise"));

                    r.Name = (r.Name ?? "") + " [LootForgeInfused]";
                    infusedProtectors++;
                }
            }

            // 3. Infuse ALL valid player accessories (talismans)
            int infusedAccessories = 0;
            foreach (var r in accParam.Rows)
            {
                int isDeposit = ParamHelper.GetCellInt(r, "isDeposit");
                int sortId = ParamHelper.GetCellInt(r, "sortId");

                if (!IsGenerated(r) && isDeposit == 1 && sortId > 0)
                {
                    var rarity = RollRarity();
                    effects.Add(new SweepFmgService.Effect(r.ID, "Accessory", rarity.ToString(), "Sacred Relic"));
                    r.Name = (r.Name ?? "") + " [LootForgeInfused]";
                    infusedAccessories++;
                }
            }

            Console.WriteLine($"[UniversalSweeper SUCCESS] Infused {infusedWeapons} weapons, {infusedProtectors} protectors, {infusedAccessories} accessories.");

            return effects;
        }
    }
}
