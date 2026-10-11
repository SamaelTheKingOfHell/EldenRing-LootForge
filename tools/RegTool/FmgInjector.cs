using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for injecting custom mod text into Elden Ring FMG archives
    /// and mirroring entries into DLC message packages (item_dlc02.msgbnd.dcx).
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class FmgInjector
    {
        public record FmgTextSpec(
            int ItemId,
            int VanillaSourceId,
            bool IsWeapon,
            string Name,
            string Caption,
            string Info
        );

        public static bool IsValidFmgText(string? text)
        {
            if (string.IsNullOrWhiteSpace(text)) return false;
            string trimmed = text.Trim();
            if (trimmed.Equals("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
            if (trimmed.StartsWith("[ERROR]", StringComparison.OrdinalIgnoreCase)) return false;
            if (trimmed.StartsWith("?")) return false;
            if (trimmed.Equals("Dummy", StringComparison.OrdinalIgnoreCase)) return false;
            return true;
        }

        public static string FormatLootForgeItemName(string rawName)
        {
            if (string.IsNullOrWhiteSpace(rawName)) return "\u2726 [LootForge] Relic";
            string cleaned = rawName.Trim();
            while (cleaned.StartsWith("\u2726") || cleaned.StartsWith("▪") || cleaned.StartsWith("★") || cleaned.StartsWith("*"))
            {
                cleaned = cleaned.Substring(1).Trim();
            }
            while (cleaned.StartsWith("[LootForge]", StringComparison.OrdinalIgnoreCase))
            {
                cleaned = cleaned.Substring("[LootForge]".Length).Trim();
                while (cleaned.StartsWith("\u2726") || cleaned.StartsWith("▪") || cleaned.StartsWith("★") || cleaned.StartsWith("*"))
                {
                    cleaned = cleaned.Substring(1).Trim();
                }
            }
            return $"\u2726 [LootForge] {cleaned}";
        }

        public static int InjectFmgEntriesIntoBnd(
            BND4 msgBnd,
            List<FmgTextSpec> fmgTexts)
        {
            var fmgFileCache = new Dictionary<string, (FMG Fmg, BinderFile File)>(StringComparer.OrdinalIgnoreCase);

            FMG? FindAndLoadFmg(string categoryName)
            {
                if (fmgFileCache.TryGetValue(categoryName, out var cached))
                    return cached.Fmg;

                var binderFile = msgBnd.Files.FirstOrDefault(f =>
                    f.Name != null &&
                    Path.GetFileName(f.Name).Equals($"{categoryName}.fmg", StringComparison.OrdinalIgnoreCase));

                if (binderFile == null) return null;

                var fmg = FMG.Read(binderFile.Bytes);
                fmgFileCache[categoryName] = (fmg, binderFile);
                return fmg;
            }

            var fmgMaps = new Dictionary<string, Dictionary<int, string?>>(StringComparer.OrdinalIgnoreCase);

            Dictionary<int, string?> GetOrCreateMap(string categoryName)
            {
                if (!fmgMaps.TryGetValue(categoryName, out var map))
                {
                    var fmg = FindAndLoadFmg(categoryName);
                    map = new Dictionary<int, string?>(fmg != null ? fmg.Entries.Count + fmgTexts.Count : fmgTexts.Count);
                    if (fmg != null)
                    {
                        foreach (var entry in fmg.Entries)
                        {
                            map[entry.ID] = entry.Text;
                        }
                    }
                    fmgMaps[categoryName] = map;
                }
                return map;
            }

            var protectorNameMap    = GetOrCreateMap("ProtectorName");
            var protectorInfoMap    = GetOrCreateMap("ProtectorInfo");
            var protectorCaptionMap = GetOrCreateMap("ProtectorCaption");
            var weaponNameMap       = GetOrCreateMap("WeaponName");
            var weaponInfoMap       = GetOrCreateMap("WeaponInfo");
            var weaponCaptionMap    = GetOrCreateMap("WeaponCaption");

            int count = 0;

            foreach (var spec in fmgTexts)
            {
                var nameMap    = spec.IsWeapon ? weaponNameMap    : protectorNameMap;
                var infoMap    = spec.IsWeapon ? weaponInfoMap    : protectorInfoMap;
                var captionMap = spec.IsWeapon ? weaponCaptionMap : protectorCaptionMap;

                string nameText = spec.Name;
                string infoText = spec.Info;
                string captionText = spec.Caption;

                // Fast O(1) lookup for vanilla name if custom mod name was not provided
                if ((string.IsNullOrWhiteSpace(nameText) || !IsValidFmgText(nameText)) && spec.VanillaSourceId > 0)
                {
                    int[] fmgIdsToTry = new int[] {
                        spec.VanillaSourceId,
                        spec.VanillaSourceId / 1000,
                        spec.VanillaSourceId / 100,
                        spec.VanillaSourceId / 10,
                        spec.VanillaSourceId * 10,
                        spec.VanillaSourceId / 10000
                    };

                    foreach (int fmgId in fmgIdsToTry)
                    {
                        if (nameMap.TryGetValue(fmgId, out var vanillaNameText) && IsValidFmgText(vanillaNameText))
                        {
                            nameText = vanillaNameText!.Trim();
                            break;
                        }
                    }
                }

                if (spec.VanillaSourceId > 0)
                {
                    if (string.IsNullOrWhiteSpace(infoText) || !IsValidFmgText(infoText))
                    {
                        if (infoMap.TryGetValue(spec.VanillaSourceId, out var vanillaInfoText) && IsValidFmgText(vanillaInfoText))
                            infoText = vanillaInfoText!;
                    }

                    if (string.IsNullOrWhiteSpace(captionText) || !IsValidFmgText(captionText))
                    {
                        if (captionMap.TryGetValue(spec.VanillaSourceId, out var vanillaCaptionText) && IsValidFmgText(vanillaCaptionText))
                            captionText = vanillaCaptionText!;
                    }
                }

                if (!IsValidFmgText(nameText))
                {
                    nameText = $"\u2726 [LootForge] {(spec.IsWeapon ? "Weapon" : "Armor")} {spec.ItemId}";
                }

                nameText = FormatLootForgeItemName(nameText);

                // O(1) assignment replaces expensive linear RemoveAll and Add
                nameMap[spec.ItemId] = nameText;
                infoMap[spec.ItemId] = infoText;
                captionMap[spec.ItemId] = captionText;

                count++;
            }

            // Reconstruct FMG entries in bulk and serialize in parallel
            foreach (var kvp in fmgFileCache)
            {
                if (fmgMaps.TryGetValue(kvp.Key, out var map))
                {
                    kvp.Value.Fmg.Entries = map.Select(e => new FMG.Entry(e.Key, e.Value)).ToList();
                }
            }

            System.Threading.Tasks.Parallel.ForEach(fmgFileCache.Values, entry =>
            {
                entry.File.Bytes = entry.Fmg.Write();
            });

            return count;
        }

        public static int InjectFmgTexts(
            string msgDir,
            string regulationOutputPath,
            List<FmgTextSpec> fmgTexts)
        {
            string itemMsgBndPath = Path.Combine(msgDir, "item.msgbnd.dcx");
            if (!File.Exists(itemMsgBndPath))
            {
                string altMsgDir = msgDir.EndsWith("engUS", StringComparison.OrdinalIgnoreCase)
                    ? msgDir.Substring(0, msgDir.Length - 5) + "engus"
                    : msgDir.Substring(0, msgDir.Length - 5) + "engUS";
                string altPath = Path.Combine(altMsgDir, "item.msgbnd.dcx");
                if (File.Exists(altPath))
                {
                    msgDir = altMsgDir;
                    itemMsgBndPath = altPath;
                }
            }

            if (!File.Exists(itemMsgBndPath))
            {
                Console.WriteLine($"[RegTool WARN] item.msgbnd.dcx not found at: {itemMsgBndPath}. Skipping FMG injection.");
                return 0;
            }

            // Create backup file before modifying
            string bakPath = itemMsgBndPath + ".bak";
            if (!File.Exists(bakPath))
            {
                File.Copy(itemMsgBndPath, bakPath, false);
                Console.WriteLine($"[RegTool] Created backup: {bakPath}");
            }

            Console.WriteLine($"[RegTool] Loading item.msgbnd.dcx from: {itemMsgBndPath}...");
            BND4 msgBnd = BND4.Read(itemMsgBndPath);

            int count = InjectFmgEntriesIntoBnd(msgBnd, fmgTexts);

            // Determine output directory alongside regulation.bin
            string baseOutDir = Path.GetDirectoryName(regulationOutputPath)!;
            string outputMsgDir = Path.Combine(baseOutDir, "msg", "engUS");
            if (!Directory.Exists(outputMsgDir))
            {
                string outputMsgDirLower = Path.Combine(baseOutDir, "msg", "engus");
                if (Directory.Exists(outputMsgDirLower)) outputMsgDir = outputMsgDirLower;
            }
            Directory.CreateDirectory(outputMsgDir);
            string outputMsgBndPath = Path.Combine(outputMsgDir, "item.msgbnd.dcx");
            msgBnd.Write(outputMsgBndPath);

            Console.WriteLine($"[RegTool] Injected {count} FMG text entries. Saved to: {outputMsgBndPath}");

            // Also mirror to DLC msg archives if available
            foreach (string dlcFile in new[] { "item_dlc02.msgbnd.dcx", "item_dlc01.msgbnd.dcx" })
            {
                string srcDlc = Path.Combine(msgDir, dlcFile);
                if (File.Exists(srcDlc))
                {
                    try
                    {
                        Console.WriteLine($"[RegTool] Mirroring {count} FMG entries to DLC archive: {dlcFile}...");
                        BND4 dlcBnd = BND4.Read(srcDlc);
                        InjectFmgEntriesIntoBnd(dlcBnd, fmgTexts);
                        string outDlc = Path.Combine(outputMsgDir, dlcFile);
                        dlcBnd.Write(outDlc);
                        Console.WriteLine($"[RegTool] Successfully mirrored into DLC archive: {outDlc}");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[RegTool WARN] Could not mirror FMG to {dlcFile}: {ex.Message}");
                    }
                }
            }

            return count;
        }
    }
}
