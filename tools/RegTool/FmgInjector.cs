using System;
using System.Collections.Generic;
using System.IO;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for injecting custom mod text into Elden Ring FMG archives
    /// and mirroring entries into DLC message packages (item_dlc01.msgbnd.dcx, item_dlc02.msgbnd.dcx).
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
            string Info,
            bool IsAccessory = false
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
            if (string.IsNullOrWhiteSpace(rawName)) return "[LootForge] Relic";
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
            return $"[LootForge] {cleaned}";
        }

        public static int InjectFmgEntriesIntoBnd(
            BND4 msgBnd,
            List<FmgTextSpec> fmgTexts)
        {
            return FmgArchiveService.InjectFmgEntriesIntoBnd(msgBnd, fmgTexts);
        }

        public static int InjectFmgTexts(
            string msgDir,
            string regulationOutputPath,
            List<FmgTextSpec> fmgTexts,
            Action<BND4>? transform = null)
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

            Console.WriteLine($"[RegTool] Loading item.msgbnd.dcx from: {itemMsgBndPath}...");
            BND4 msgBnd = BND4.Read(itemMsgBndPath);

            int count = InjectFmgEntriesIntoBnd(msgBnd, fmgTexts);
            transform?.Invoke(msgBnd);

            // Determine output directory alongside regulation.bin
            string baseOutDir = Path.GetDirectoryName(regulationOutputPath)!;
            string sourceLanguage = Path.GetFileName(Path.TrimEndingDirectorySeparator(msgDir));
            string outputMsgDir = Path.Combine(baseOutDir, "msg", sourceLanguage == "engus" ? "engus" : "engUS");
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
                        transform?.Invoke(dlcBnd);
                        string outDlc = Path.Combine(outputMsgDir, dlcFile);
                        dlcBnd.Write(outDlc);
                        Console.WriteLine($"[RegTool] Successfully mirrored into DLC archive: {outDlc}");
                    }
                    catch (Exception ex)
                    {
                        throw new IOException($"Could not patch DLC message archive {dlcFile}.", ex);
                    }
                }
            }

            return count;
        }

        public static int ExecuteSyncDlcMsg(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("msg-dir", out string? msgDir) || string.IsNullOrEmpty(msgDir))
            {
                Console.Error.WriteLine("Missing required --msg-dir.");
                return 1;
            }

            string baseItemMsg = Path.Combine(msgDir, "item.msgbnd.dcx");
            if (!File.Exists(baseItemMsg))
            {
                Console.Error.WriteLine($"item.msgbnd.dcx not found in {msgDir}");
                return 1;
            }

            Console.WriteLine($"[RegTool] Loading base FMG archive: {baseItemMsg}...");
            BND4 baseBnd = BND4.Read(baseItemMsg);

            var specs = new List<FmgTextSpec>();

            void ExtractSpecs(string nameCat, string infoCat, string capCat, bool isWep, bool isAcc)
            {
                var nameFile = baseBnd.Files.FirstOrDefault(f => Path.GetFileName(f.Name).Equals($"{nameCat}.fmg", StringComparison.OrdinalIgnoreCase));
                var infoFile = baseBnd.Files.FirstOrDefault(f => Path.GetFileName(f.Name).Equals($"{infoCat}.fmg", StringComparison.OrdinalIgnoreCase));
                var capFile = baseBnd.Files.FirstOrDefault(f => Path.GetFileName(f.Name).Equals($"{capCat}.fmg", StringComparison.OrdinalIgnoreCase));

                if (nameFile == null) return;
                var nameFmg = FMG.Read(nameFile.Bytes);
                var infoFmg = infoFile != null ? FMG.Read(infoFile.Bytes) : null;
                var capFmg = capFile != null ? FMG.Read(capFile.Bytes) : null;

                var infoMap = infoFmg?.Entries.Where(e => e.ID >= 9000000).ToDictionary(e => e.ID, e => e.Text) ?? new();
                var capMap = capFmg?.Entries.Where(e => e.ID >= 9000000).ToDictionary(e => e.ID, e => e.Text) ?? new();

                foreach (var entry in nameFmg.Entries.Where(e => e.ID >= 9000000 && !string.IsNullOrWhiteSpace(e.Text)))
                {
                    infoMap.TryGetValue(entry.ID, out string? info);
                    capMap.TryGetValue(entry.ID, out string? cap);
                    specs.Add(new FmgTextSpec(
                        ItemId: entry.ID,
                        VanillaSourceId: 0,
                        IsWeapon: isWep,
                        Name: entry.Text!,
                        Caption: cap ?? "",
                        Info: info ?? "",
                        IsAccessory: isAcc
                    ));
                }
            }

            ExtractSpecs("AccessoryName", "AccessoryInfo", "AccessoryCaption", false, true);
            ExtractSpecs("ProtectorName", "ProtectorInfo", "ProtectorCaption", false, false);
            ExtractSpecs("WeaponName", "WeaponInfo", "WeaponCaption", true, false);

            Console.WriteLine($"[RegTool] Extracted {specs.Count} custom items (ID >= 9000000) from base archive.");

            foreach (string dlcFile in new[] { "item_dlc02.msgbnd.dcx", "item_dlc01.msgbnd.dcx" })
            {
                string dlcPath = Path.Combine(msgDir, dlcFile);
                if (File.Exists(dlcPath))
                {
                    Console.WriteLine($"[RegTool] Mirroring into {dlcFile}...");
                    BND4 dlcBnd = BND4.Read(dlcPath);
                    int mirrored = FmgArchiveService.InjectFmgEntriesIntoBnd(dlcBnd, specs);
                    dlcBnd.Write(dlcPath);
                    Console.WriteLine($"[RegTool SUCCESS] Synced {mirrored} entries across all variant FMGs in {dlcFile}!");
                }
            }

            return 0;
        }
    }
}
