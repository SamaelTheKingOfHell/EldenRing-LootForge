using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service responsible for locating, loading, injecting, and serializing
    /// FMG message archives across base and DLC packages (item.msgbnd.dcx, item_dlc01.msgbnd.dcx, item_dlc02.msgbnd.dcx).
    /// Ensures all variant FMG files (_dlc01, _dlc02) are kept in full parity.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class FmgArchiveService
    {
        public static bool MatchesCategory(string? filePath, string categoryName)
        {
            if (string.IsNullOrEmpty(filePath)) return false;
            string fileName = Path.GetFileNameWithoutExtension(filePath);
            return fileName.Equals(categoryName, StringComparison.OrdinalIgnoreCase) ||
                   fileName.StartsWith($"{categoryName}_dlc", StringComparison.OrdinalIgnoreCase);
        }

        public static int InjectFmgEntriesIntoBnd(
            BND4 msgBnd,
            List<FmgInjector.FmgTextSpec> fmgTexts)
        {
            var categoryToFmgs = new Dictionary<string, List<(FMG Fmg, BinderFile File)>>(StringComparer.OrdinalIgnoreCase);

            List<(FMG Fmg, BinderFile File)> GetOrLoadFmgs(string categoryName)
            {
                if (categoryToFmgs.TryGetValue(categoryName, out var list))
                    return list;

                list = new List<(FMG Fmg, BinderFile File)>();
                var matchingFiles = msgBnd.Files.Where(f => MatchesCategory(f.Name, categoryName)).ToList();

                foreach (var bf in matchingFiles)
                {
                    var fmg = FMG.Read(bf.Bytes);
                    list.Add((fmg, bf));
                }

                categoryToFmgs[categoryName] = list;
                return list;
            }

            var fileMaps = new Dictionary<(string Category, string FileName), Dictionary<int, string?>>();

            void EnsureCategoryMapsLoaded(string categoryName)
            {
                var fmgs = GetOrLoadFmgs(categoryName);
                foreach (var (fmg, file) in fmgs)
                {
                    var key = (categoryName, file.Name ?? "");
                    if (!fileMaps.ContainsKey(key))
                    {
                        var map = new Dictionary<int, string?>(fmg.Entries.Count + fmgTexts.Count);
                        foreach (var entry in fmg.Entries)
                        {
                            map[entry.ID] = entry.Text;
                        }
                        fileMaps[key] = map;
                    }
                }
            }

            string[] categories = [
                "ProtectorName", "ProtectorInfo", "ProtectorCaption",
                "WeaponName", "WeaponInfo", "WeaponCaption",
                "AccessoryName", "AccessoryInfo", "AccessoryCaption"
            ];

            foreach (var cat in categories)
            {
                EnsureCategoryMapsLoaded(cat);
            }

            int count = 0;

            foreach (var spec in fmgTexts)
            {
                string nameCat = spec.IsAccessory ? "AccessoryName" : (spec.IsWeapon ? "WeaponName" : "ProtectorName");
                string infoCat = spec.IsAccessory ? "AccessoryInfo" : (spec.IsWeapon ? "WeaponInfo" : "ProtectorInfo");
                string captionCat = spec.IsAccessory ? "AccessoryCaption" : (spec.IsWeapon ? "WeaponCaption" : "ProtectorCaption");

                string nameText = spec.Name;
                string infoText = spec.Info;
                string captionText = spec.Caption;

                // Lookup vanilla text if needed
                if ((string.IsNullOrWhiteSpace(nameText) || !FmgInjector.IsValidFmgText(nameText)) && spec.VanillaSourceId > 0)
                {
                    int[] fmgIdsToTry = [
                        spec.VanillaSourceId,
                        spec.VanillaSourceId / 1000,
                        spec.VanillaSourceId / 100,
                        spec.VanillaSourceId / 10,
                        spec.VanillaSourceId * 10,
                        spec.VanillaSourceId / 10000
                    ];

                    foreach (var kvp in fileMaps.Where(k => k.Key.Category.Equals(nameCat, StringComparison.OrdinalIgnoreCase)))
                    {
                        foreach (int fmgId in fmgIdsToTry)
                        {
                            if (kvp.Value.TryGetValue(fmgId, out var vanillaNameText) && FmgInjector.IsValidFmgText(vanillaNameText))
                            {
                                nameText = vanillaNameText!.Trim();
                                break;
                            }
                        }
                        if (FmgInjector.IsValidFmgText(nameText)) break;
                    }
                }

                if (spec.VanillaSourceId > 0)
                {
                    if (string.IsNullOrWhiteSpace(infoText) || !FmgInjector.IsValidFmgText(infoText))
                    {
                        foreach (var kvp in fileMaps.Where(k => k.Key.Category.Equals(infoCat, StringComparison.OrdinalIgnoreCase)))
                        {
                            if (kvp.Value.TryGetValue(spec.VanillaSourceId, out var vanillaInfoText) && FmgInjector.IsValidFmgText(vanillaInfoText))
                            {
                                infoText = vanillaInfoText!;
                                break;
                            }
                        }
                    }

                    if (string.IsNullOrWhiteSpace(captionText) || !FmgInjector.IsValidFmgText(captionText))
                    {
                        foreach (var kvp in fileMaps.Where(k => k.Key.Category.Equals(captionCat, StringComparison.OrdinalIgnoreCase)))
                        {
                            if (kvp.Value.TryGetValue(spec.VanillaSourceId, out var vanillaCaptionText) && FmgInjector.IsValidFmgText(vanillaCaptionText))
                            {
                                captionText = vanillaCaptionText!;
                                break;
                            }
                        }
                    }
                }

                if (!FmgInjector.IsValidFmgText(nameText))
                {
                    nameText = $"[LootForge] {(spec.IsAccessory ? "Accessory" : (spec.IsWeapon ? "Weapon" : "Armor"))} {spec.ItemId}";
                }

                nameText = FmgInjector.FormatLootForgeItemName(nameText);

                // Inject into ALL matching files for this category across base and DLC
                foreach (var kvp in fileMaps.Where(k => k.Key.Category.Equals(nameCat, StringComparison.OrdinalIgnoreCase)))
                {
                    kvp.Value[spec.ItemId] = nameText;
                }
                foreach (var kvp in fileMaps.Where(k => k.Key.Category.Equals(infoCat, StringComparison.OrdinalIgnoreCase)))
                {
                    kvp.Value[spec.ItemId] = infoText;
                }
                foreach (var kvp in fileMaps.Where(k => k.Key.Category.Equals(captionCat, StringComparison.OrdinalIgnoreCase)))
                {
                    kvp.Value[spec.ItemId] = captionText;
                }

                count++;
            }

            // Reconstruct and serialize all modified FMG files
            var allModifiedFmgs = new List<(FMG Fmg, BinderFile File)>();
            foreach (var kvp in categoryToFmgs)
            {
                foreach (var (fmg, file) in kvp.Value)
                {
                    var mapKey = (kvp.Key, file.Name ?? "");
                    if (fileMaps.TryGetValue(mapKey, out var map))
                    {
                        fmg.Entries = map.Select(e => new FMG.Entry(e.Key, e.Value)).ToList();
                        allModifiedFmgs.Add((fmg, file));
                    }
                }
            }

            System.Threading.Tasks.Parallel.ForEach(allModifiedFmgs, item =>
            {
                item.File.Bytes = item.Fmg.Write();
            });

            return count;
        }
    }
}
