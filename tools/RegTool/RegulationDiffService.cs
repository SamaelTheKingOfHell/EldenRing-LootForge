using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service that accurately computes and prints the exact parameter diffs
    /// between two regulation.bin files. Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class RegulationDiffService
    {
        public static int ExecuteDiffReg(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input1", out string? input1) || string.IsNullOrEmpty(input1) || !File.Exists(input1))
            {
                Console.Error.WriteLine("[RegTool ERROR] Missing or invalid --input1 path.");
                return 1;
            }

            if (!options.TryGetValue("input2", out string? input2) || string.IsNullOrEmpty(input2) || !File.Exists(input2))
            {
                Console.Error.WriteLine("[RegTool ERROR] Missing or invalid --input2 path.");
                return 1;
            }

            string defsDir = options.TryGetValue("defs", out string? dd) && !string.IsNullOrEmpty(dd) ? dd : @"tools\vendor\Paramdex\ER\Defs";
            string targetTable = options.TryGetValue("table", out string? tb) ? tb : "";

            Console.WriteLine($"[DiffReg] Comparing:");
            Console.WriteLine($"  Base:   {input1}");
            Console.WriteLine($"  Target: {input2}");

            BND4 bnd1 = RegulationDecryptor.DecryptERRegulation(input1);
            BND4 bnd2 = RegulationDecryptor.DecryptERRegulation(input2);

            var tables1 = bnd1.Files.Where(f => f.Name.EndsWith(".param", StringComparison.OrdinalIgnoreCase)).Select(f => Path.GetFileNameWithoutExtension(f.Name)).ToHashSet(StringComparer.OrdinalIgnoreCase);
            var tables2 = bnd2.Files.Where(f => f.Name.EndsWith(".param", StringComparison.OrdinalIgnoreCase)).Select(f => Path.GetFileNameWithoutExtension(f.Name)).ToHashSet(StringComparer.OrdinalIgnoreCase);

            var allTables = tables1.Union(tables2).OrderBy(t => t).ToList();
            if (!string.IsNullOrEmpty(targetTable))
            {
                allTables = allTables.Where(t => t.Equals(targetTable, StringComparison.OrdinalIgnoreCase)).ToList();
            }

            int totalTableDiffs = 0;

            foreach (var tableName in allTables)
            {
                var file1 = bnd1.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));
                var file2 = bnd2.Files.FirstOrDefault(f => f.Name.EndsWith($"{tableName}.param", StringComparison.OrdinalIgnoreCase));

                if (file1 == null)
                {
                    Console.WriteLine($"[DiffReg] Table '{tableName}' only exists in Target!");
                    totalTableDiffs++;
                    continue;
                }
                if (file2 == null)
                {
                    Console.WriteLine($"[DiffReg] Table '{tableName}' only exists in Base!");
                    totalTableDiffs++;
                    continue;
                }

                var param1 = PARAM.Read(file1.Bytes);
                var param2 = PARAM.Read(file2.Bytes);

                string defBaseName = tableName.StartsWith("ItemLotParam", StringComparison.OrdinalIgnoreCase) ? "ItemLotParam"
                    : tableName.StartsWith("BehaviorParam", StringComparison.OrdinalIgnoreCase) ? "BehaviorParam"
                    : tableName.StartsWith("AtkParam", StringComparison.OrdinalIgnoreCase) ? "AtkParam"
                    : tableName.StartsWith("SpEffectParam", StringComparison.OrdinalIgnoreCase) ? "SpEffect"
                    : tableName;
                string xmlFile = Path.Combine(defsDir, $"{defBaseName}.xml");
                if (File.Exists(xmlFile))
                {
                    try
                    {
                        var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                        param1.ApplyParamdefSomewhatCarefully(def);
                        param2.ApplyParamdefSomewhatCarefully(def);
                    }
                    catch { }
                }

                var dict1 = param1.ToRowDictionary();
                var dict2 = param2.ToRowDictionary();

                var addedIds = dict2.Keys.Except(dict1.Keys).ToList();
                var removedIds = dict1.Keys.Except(dict2.Keys).ToList();
                var commonIds = dict1.Keys.Intersect(dict2.Keys).ToList();

                var modifiedRows = new List<(PARAM.Row R1, PARAM.Row R2, List<(string Field, object? V1, object? V2)> Diffs)>();

                foreach (var id in commonIds)
                {
                    var r1 = dict1[id];
                    var r2 = dict2[id];

                    var cellDiffs = new List<(string, object?, object?)>();
                    if (!string.Equals(r1.Name, r2.Name, StringComparison.Ordinal))
                    {
                        cellDiffs.Add(("_row_name", r1.Name, r2.Name));
                    }

                    if (r1.Cells != null && r2.Cells != null)
                    {
                        int count = Math.Min(r1.Cells.Count, r2.Cells.Count);
                        for (int i = 0; i < count; i++)
                        {
                            var c1 = r1.Cells[i];
                            var c2 = r2.Cells[i];
                            string fieldName = c1.Def?.InternalName ?? $"Cell_{i}";
                            if (fieldName.StartsWith("pad", StringComparison.OrdinalIgnoreCase)) continue;

                            bool diff = false;
                            if (c1.Value is byte[] b1 && c2.Value is byte[] b2)
                            {
                                diff = !b1.SequenceEqual(b2);
                            }
                            else
                            {
                                diff = !Equals(c1.Value, c2.Value);
                            }

                            if (diff)
                            {
                                cellDiffs.Add((fieldName, c1.Value, c2.Value));
                            }
                        }
                    }

                    if (cellDiffs.Count > 0)
                    {
                        modifiedRows.Add((r1, r2, cellDiffs));
                    }
                }

                if (addedIds.Count > 0 || removedIds.Count > 0 || modifiedRows.Count > 0)
                {
                    totalTableDiffs++;
                    Console.WriteLine($"\n========================================================");
                    Console.WriteLine($"TABLE: {tableName} (Rows: Base={param1.Rows.Count}, Target={param2.Rows.Count})");
                    Console.WriteLine($"  Added Rows: {addedIds.Count}, Removed Rows: {removedIds.Count}, Modified Rows: {modifiedRows.Count}");
                    
                    if (addedIds.Count > 0 && addedIds.Count <= 20)
                    {
                        Console.WriteLine($"  Added IDs: {string.Join(", ", addedIds.Take(20))}");
                    }
                    else if (addedIds.Count > 20)
                    {
                        Console.WriteLine($"  Added IDs (sample 20): {string.Join(", ", addedIds.Take(20))}... (+{addedIds.Count - 20} more)");
                    }

                    if (removedIds.Count > 0)
                    {
                        Console.WriteLine($"  Removed IDs: {string.Join(", ", removedIds.Take(20))}");
                    }

                    if (modifiedRows.Count > 0)
                    {
                        Console.WriteLine($"  Modified Rows Details (showing first 30):");
                        foreach (var m in modifiedRows.Take(30))
                        {
                            Console.WriteLine($"    Row ID={m.R1.ID} ('{m.R1.Name}'):");
                            foreach (var d in m.Diffs.Take(10))
                            {
                                Console.WriteLine($"      {d.Field}: '{d.V1}' -> '{d.V2}'");
                            }
                            if (m.Diffs.Count > 10)
                            {
                                Console.WriteLine($"      ... (+{m.Diffs.Count - 10} more fields changed)");
                            }
                        }
                    }
                }
            }

            Console.WriteLine($"\n[DiffReg DONE] Total tables with differences: {totalTableDiffs}");
            return 0;
        }
    }
}
