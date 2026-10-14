using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service that injects high-tier weapon loot pools into boss encounter drop tables
    /// across the Lands Between, scaled strictly by world progression tier.
    /// Injects exclusively into ItemLotParam_enemy with zero repetition across bosses.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class BossLootPoolService
    {
        public enum ProgressionTier
        {
            Early = 1,
            Mid = 2,
            Late = 3,
            Endgame = 4
        }

        public record WeaponDefinition(int Id, string Name, ProgressionTier Tier);

        public static readonly List<WeaponDefinition> CURATED_WEAPONS = new()
        {
            new(8000000, "Bloodhound's Fang", ProgressionTier.Early),
            new(9000000, "Uchigatana", ProgressionTier.Early),
            new(3010000, "Claymore", ProgressionTier.Early),
            new(3020000, "Lordsworn's Greatsword", ProgressionTier.Early),
            new(10000000, "Twinblade", ProgressionTier.Early),
            new(2020000, "Reduvia", ProgressionTier.Early),
            new(6000000, "Great Epee", ProgressionTier.Early),
            new(9040000, "Nagakiba", ProgressionTier.Early),
            new(4100000, "Grafted Blade Greatsword", ProgressionTier.Early),
            new(18010000, "Golden Halberd", ProgressionTier.Early),
            new(13010000, "Nightrider Flail", ProgressionTier.Early),
            new(8010000, "Dismounter", ProgressionTier.Early),
            new(4010000, "Zweihander", ProgressionTier.Early),
            new(11020000, "Morning Star", ProgressionTier.Early),

            new(9060000, "Moonveil", ProgressionTier.Mid),
            new(3090000, "Dark Moon Greatsword", ProgressionTier.Mid),
            new(4070000, "Starscourge Greatsword", ProgressionTier.Mid),
            new(4060000, "Godslayer's Greatsword", ProgressionTier.Mid),
            new(2070000, "Carian Knight's Sword", ProgressionTier.Mid),
            new(20010000, "Winged Scythe", ProgressionTier.Mid),
            new(2080000, "Sword of Night and Flame", ProgressionTier.Mid),
            new(16040000, "Cross-Naginata", ProgressionTier.Mid),
            new(4000000, "Greatsword (Guts)", ProgressionTier.Mid),
            new(8040000, "Magma Wyrm's Scalesword", ProgressionTier.Mid),
            new(4080000, "Ruins Greatsword", ProgressionTier.Mid),
            new(12210000, "Rotten Battle Hammer", ProgressionTier.Mid),
            new(18060000, "Guardian's Swordspear", ProgressionTier.Mid),
            new(10040000, "Eleonora's Poleblade", ProgressionTier.Mid),

            new(3140000, "Blasphemous Blade", ProgressionTier.Late),
            new(9080000, "Rivers of Blood", ProgressionTier.Late),
            new(3150000, "Marais Executioner's Sword", ProgressionTier.Late),
            new(8070000, "Morgott's Cursed Sword", ProgressionTier.Late),
            new(16140000, "Bolt of Gransax", ProgressionTier.Late),
            new(3060000, "Ordovis's Greatsword", ProgressionTier.Late),
            new(10020000, "Godskin Peeler", ProgressionTier.Late),
            new(6010000, "Godskin Stitcher", ProgressionTier.Late),
            new(16130000, "Inquisitor's Girandole", ProgressionTier.Late),
            new(23000000, "Prelate's Inferno Crozier", ProgressionTier.Late),
            new(17020000, "Siluria's Tree", ProgressionTier.Late),
            new(17010000, "Vyke's War Spear", ProgressionTier.Late),
            new(3120000, "Death's Poker", ProgressionTier.Late),

            new(9070000, "Hand of Malenia", ProgressionTier.Endgame),
            new(4090000, "Maliketh's Black Blade", ProgressionTier.Endgame),
            new(3160000, "Sacred Relic Sword", ProgressionTier.Endgame),
            new(17040000, "Mohgwyn's Sacred Spear", ProgressionTier.Endgame),
            new(23050000, "Giant-Crusher", ProgressionTier.Endgame),
            new(7030000, "Dragon King's Cragblade", ProgressionTier.Endgame),
            new(3170000, "Golden Order Greatsword", ProgressionTier.Endgame),
            new(8050000, "Zamor Curved Sword", ProgressionTier.Endgame),
            new(21120000, "Veteran's Prosthesis", ProgressionTier.Endgame),
            new(4050000, "Fallingstar Beast Jaw", ProgressionTier.Endgame),
            new(7040000, "Eclipse Shotel", ProgressionTier.Endgame),
            new(4040000, "Royal Greatsword", ProgressionTier.Endgame)
        };

        public static ProgressionTier DetermineTier(int lotId, string? name)
        {
            string n = (name ?? "").ToLowerInvariant();

            if (lotId == 20330 || lotId == 1037420400 || n.Contains("groveside") || (n.Contains("beastman of farum azula") && !n.Contains("dragonbarrow")))
                return ProgressionTier.Early;

            if (n.Contains("haligtree") || n.Contains("malenia") || n.Contains("maliketh") || n.Contains("mohg") ||
                n.Contains("placidusax") || n.Contains("elden beast") || n.Contains("snowfield") || n.Contains("mountaintop") ||
                n.Contains("castle sol") || n.Contains("niall") || n.Contains("forlorn") || n.Contains("spiritcaller") ||
                n.Contains("zamor") || n.Contains("farum azula"))
                return ProgressionTier.Endgame;

            if (n.Contains("altus") || n.Contains("leyndell") || n.Contains("volcano") || n.Contains("gelmir") ||
                n.Contains("rykard") || n.Contains("godfrey") || n.Contains("ordovis") || n.Contains("auriza") ||
                n.Contains("elemer") || n.Contains("shaded castle") || n.Contains("sage's cave") || n.Contains("perfumer") ||
                n.Contains("seethewater") || n.Contains("old altus") || n.Contains("sealed tunnel"))
                return ProgressionTier.Late;

            if (n.Contains("liurnia") || n.Contains("raya lucaria") || n.Contains("caria") || n.Contains("rennala") ||
                n.Contains("radahn") || n.Contains("caelid") || n.Contains("redmane") || n.Contains("makar") ||
                n.Contains("siofra") || n.Contains("ainsel") || n.Contains("stillwater") || n.Contains("lakeside") ||
                n.Contains("abandoned cave") || n.Contains("dragonbarrow") || n.Contains("gargoyle"))
                return ProgressionTier.Mid;

            if (n.Contains("limgrave") || n.Contains("weeping") || n.Contains("stormveil") || n.Contains("morne") ||
                n.Contains("godrick") || n.Contains("margit") || n.Contains("darriwil") || n.Contains("highroad") ||
                n.Contains("deathtouched") || n.Contains("tombsward") || n.Contains("earthbore") || n.Contains("murkwater") ||
                n.Contains("chapel of anticipation") || n.Contains("gatefront"))
                return ProgressionTier.Early;

            if (lotId >= 20470 && lotId < 20600) return ProgressionTier.Endgame;
            if ((lotId >= 20100 && lotId < 20300) || (lotId >= 20400 && lotId < 20470) || (lotId >= 20630 && lotId < 20700)) return ProgressionTier.Late;
            if (lotId >= 20360 && lotId < 20400) return ProgressionTier.Mid;
            return ProgressionTier.Early;
        }

        public static int ExecuteInjectBossLootPools(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to regulation.bin.");
                return 1;
            }
            string outputPath = options.TryGetValue("output", out string? op) && !string.IsNullOrEmpty(op) ? op : inputPath;
            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            int weaponsPerBoss = options.TryGetValue("count", out string? cntStr) && int.TryParse(cntStr, out int parsedCnt) ? Math.Clamp(parsedCnt, 1, 5) : 3;

            Console.WriteLine($"[BossLootPoolService] Loading and decrypting: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            var enemyFile = bnd.Files.FirstOrDefault(f => f.Name.EndsWith("ItemLotParam_enemy.param", StringComparison.OrdinalIgnoreCase));
            if (enemyFile == null) throw new Exception("Table ItemLotParam_enemy not found in regulation.");
            var enemyParam = PARAM.Read(enemyFile.Bytes);
            string xmlFile = Path.Combine(defsDir, "ItemLotParam.xml");
            if (File.Exists(xmlFile))
            {
                var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                enemyParam.ApplyParamdefSomewhatCarefully(def);
            }

            var rowMap = new Dictionary<int, PARAM.Row>(enemyParam.Rows.Count);
            foreach (var r in enemyParam.Rows)
                rowMap[r.ID] = r;

            // Target boss encounters exclusively in ItemLotParam_enemy (NEVER ItemLotParam_map chests)
            var targetBossLots = new Dictionary<int, (string Name, ProgressionTier Tier)>();

            // 1. Explicit priority bosses
            targetBossLots[20330] = ("[Groveside Cave - Beastman of Farum Azula] Flamedrake Talisman", ProgressionTier.Early);
            targetBossLots[1037420400] = ("Groveside Cave - Beastman of Farum Azula", ProgressionTier.Early);

            // 2. Discover boss reward rows in ItemLotParam_enemy (100% weapon/accessory drops)
            foreach (var r in enemyParam.Rows)
            {
                int p1 = ParamHelper.GetCellInt(r, "lotItemBasePoint01");
                int itm1 = ParamHelper.GetCellInt(r, "lotItemId01");
                int cat1 = ParamHelper.GetCellInt(r, "lotItemCategory01");

                if (itm1 > 0 && p1 >= 1000 && (cat1 == 2 || cat1 == 4))
                {
                    if (!targetBossLots.ContainsKey(r.ID))
                    {
                        var tier = DetermineTier(r.ID, r.Name);
                        targetBossLots[r.ID] = (r.Name ?? $"Boss Lot {r.ID}", tier);
                    }
                }
            }

            Console.WriteLine($"[BossLootPoolService] Discovered {targetBossLots.Count} boss loot targets in ItemLotParam_enemy.");

            int totalChainedRowsAdded = 0;
            int bossesEnriched = 0;
            var rng = new Random(1337);
            var usedWeaponIds = new HashSet<int>();

            foreach (var kvp in targetBossLots)
            {
                int baseLotId = kvp.Key;
                string bossName = kvp.Value.Name;
                ProgressionTier tier = kvp.Value.Tier;

                if (!rowMap.TryGetValue(baseLotId, out var baseRow))
                    continue;

                // Pick distinct, non-repeating weapons for this boss across the entire run
                var candidateWeapons = CURATED_WEAPONS.Where(w => w.Tier == tier && !usedWeaponIds.Contains(w.Id)).OrderBy(_ => rng.Next()).ToList();
                if (candidateWeapons.Count < weaponsPerBoss)
                {
                    var fallbackPool = CURATED_WEAPONS.Where(w => !usedWeaponIds.Contains(w.Id)).OrderBy(_ => rng.Next()).ToList();
                    candidateWeapons.AddRange(fallbackPool.Take(weaponsPerBoss - candidateWeapons.Count));
                }

                var chosenWeapons = candidateWeapons.Take(weaponsPerBoss).ToList();
                if (chosenWeapons.Count == 0)
                    continue;

                foreach (var w in chosenWeapons)
                    usedWeaponIds.Add(w.Id);

                int addedForThisBoss = 0;
                for (int offset = 1; offset <= chosenWeapons.Count; offset++)
                {
                    int chainedId = baseLotId + offset;
                    var weapon = chosenWeapons[offset - 1];

                    if (!rowMap.TryGetValue(chainedId, out var chainedRow))
                    {
                        chainedRow = new PARAM.Row(baseRow) { ID = chainedId };
                        enemyParam.Rows.Add(chainedRow);
                        rowMap[chainedId] = chainedRow;
                    }

                    chainedRow.Name = $"[Boss Pool T{(int)tier}] {weapon.Name} (for {bossName})";
                    for (int s = 1; s <= 8; s++)
                    {
                        ParamHelper.SetCellIfExists(chainedRow, $"lotItemId0{s}", 0);
                        ParamHelper.SetCellIfExists(chainedRow, $"lotItemCategory0{s}", 0);
                        ParamHelper.SetCellIfExists(chainedRow, $"lotItemBasePoint0{s}", (ushort)0);
                        ParamHelper.SetCellIfExists(chainedRow, $"lotItemNum0{s}", (byte)0);
                        ParamHelper.SetCellIfExists(chainedRow, $"getItemFlagId0{s}", 0u);
                    }

                    ParamHelper.SetCellIfExists(chainedRow, "lotItemId01", weapon.Id);
                    ParamHelper.SetCellIfExists(chainedRow, "lotItemCategory01", 2);
                    ParamHelper.SetCellIfExists(chainedRow, "lotItemBasePoint01", (ushort)1000);
                    ParamHelper.SetCellIfExists(chainedRow, "lotItemNum01", (byte)1);
                    ParamHelper.SetCellIfExists(chainedRow, "getItemFlagId01", 0u);

                    addedForThisBoss++;
                    totalChainedRowsAdded++;
                }

                bossesEnriched++;
                if (bossesEnriched <= 20 || baseLotId == 1037420400 || baseLotId == 20330)
                {
                    Console.WriteLine($"[ENRICHED BOSS] Lot {baseLotId} ({bossName}) -> Tier: {tier} (+{addedForThisBoss} chained weapons)");
                    foreach (var w in chosenWeapons)
                        Console.WriteLine($"   * Dropping: {w.Name} (ID: {w.Id})");
                }
            }

            Console.WriteLine($"\n[BossLootPoolService] Successfully enriched {bossesEnriched} bosses with {totalChainedRowsAdded} unique chained weapon drops!");

            enemyFile.Bytes = enemyParam.Write();

            string? outDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outDir) && !Directory.Exists(outDir))
                Directory.CreateDirectory(outDir);

            Console.WriteLine($"[BossLootPoolService] Encrypting and saving updated regulation to: {outputPath}...");
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);
            Console.WriteLine($"[BossLootPoolService SUCCESS] Saved {new FileInfo(outputPath).Length} bytes. Boss loot pools are live!");

            return 0;
        }
    }
}
