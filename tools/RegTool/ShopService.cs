using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service for managing and injecting shop lineup rows directly into ShopLineupParam.
    /// Ensures merchants sell injected equipment in their native ESD event ranges.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class ShopService
    {
        public static int ExecuteAddShopItem(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to regulation.bin.");
                return 1;
            }

            string outputPath = options.TryGetValue("output", out string? outP) && !string.IsNullOrEmpty(outP)
                ? outP
                : inputPath;

            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd)
                ? dd
                : @"tools\vendor\Paramdex\ER\Defs";

            if (!int.TryParse(options.GetValueOrDefault("shop-row", "100521"), out int shopRowId))
            {
                Console.Error.WriteLine("Invalid --shop-row ID.");
                return 1;
            }

            if (!int.TryParse(options.GetValueOrDefault("equip-id", "9092000"), out int equipId))
            {
                Console.Error.WriteLine("Invalid --equip-id.");
                return 1;
            }

            byte equipType = byte.TryParse(options.GetValueOrDefault("equip-type", "1"), out byte eqT) ? eqT : (byte)1;
            int cost = int.TryParse(options.GetValueOrDefault("cost", "200"), out int cst) ? cst : 200;
            string rowName = options.GetValueOrDefault("name", "[LootForge] [Test: Shop] Merchant Kalé (Church of Elleh)");

            Console.WriteLine($"[RegTool] Decrypting regulation: {inputPath}...");
            BND4 bnd = RegulationDecryptor.DecryptERRegulation(inputPath);

            var file = bnd.Files.FirstOrDefault(f => f.Name.EndsWith("ShopLineupParam.param", StringComparison.OrdinalIgnoreCase));
            if (file == null)
            {
                Console.Error.WriteLine("ShopLineupParam.param not found in regulation.");
                return 1;
            }

            string xmlFile = Path.Combine(defsDir, "ShopLineupParam.xml");
            if (!File.Exists(xmlFile))
            {
                Console.Error.WriteLine($"ShopLineupParam.xml definition not found at: {xmlFile}");
                return 1;
            }

            var param = PARAM.Read(file.Bytes);
            var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
            param.ApplyParamdefSomewhatCarefully(def);

            var existingRow = param.Rows.FirstOrDefault(r => r.ID == shopRowId);
            PARAM.Row shopRow;

            if (existingRow != null)
            {
                Console.WriteLine($"[RegTool] Updating existing shop row ID={shopRowId}...");
                shopRow = existingRow;
                shopRow.Name = rowName;
            }
            else
            {
                var templateRow = param.Rows.FirstOrDefault(r => r.ID >= 100500 && r.ID <= 100524)
                               ?? param.Rows.FirstOrDefault();
                if (templateRow == null)
                {
                    Console.Error.WriteLine("Cannot find template row for ShopLineupParam.");
                    return 1;
                }

                Console.WriteLine($"[RegTool] Creating new shop row ID={shopRowId} from template ID={templateRow.ID}...");
                shopRow = new PARAM.Row(templateRow)
                {
                    ID = shopRowId,
                    Name = rowName
                };
                param.Rows.Add(shopRow);
            }

            ParamHelper.SetCellIfExists(shopRow, "equipId", equipId);
            ParamHelper.SetCellIfExists(shopRow, "equipType", equipType);
            ParamHelper.SetCellIfExists(shopRow, "value", cost);
            ParamHelper.SetCellIfExists(shopRow, "mtrlId", -1);
            ParamHelper.SetCellIfExists(shopRow, "eventFlag_forRelease", 0u);
            ParamHelper.SetCellIfExists(shopRow, "eventFlag_forStock", 0u);
            ParamHelper.SetCellIfExists(shopRow, "sellQuantity", (short)-1);
            ParamHelper.SetCellIfExists(shopRow, "costType", (byte)0);
            ParamHelper.SetCellIfExists(shopRow, "setNum", (ushort)1);
            ParamHelper.SetCellIfExists(shopRow, "value_Add", 0);
            ParamHelper.SetCellIfExists(shopRow, "value_Magnification", 1.0f);
            ParamHelper.SetCellIfExists(shopRow, "iconId", -1);
            ParamHelper.SetCellIfExists(shopRow, "nameMsgId", -1);
            ParamHelper.SetCellIfExists(shopRow, "menuTitleMsgId", -1);
            ParamHelper.SetCellIfExists(shopRow, "menuIconId", (short)-1);

            Console.WriteLine($"[RegTool] Shop row configured: ID={shopRow.ID}, equipId={equipId}, equipType={equipType}, cost={cost}");

            file.Bytes = param.Write();

            Console.WriteLine($"[RegTool] Encrypting and saving updated regulation to: {outputPath}...");
            RegulationDecryptor.EncryptERRegulation(outputPath, bnd);
            Console.WriteLine($"[RegTool SUCCESS] Successfully wrote shop row {shopRowId} to {outputPath}!");

            return 0;
        }
    }
}
