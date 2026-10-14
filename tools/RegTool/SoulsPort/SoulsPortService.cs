using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool.SoulsPort
{
    /// <summary>
    /// Service orchestrating selective archive extraction, FLVER2 modernization,
    /// and metadata synthesis for legacy Souls sets into Elden Ring.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class SoulsPortService
    {
        public class ArmorPieceSpec
        {
            public string Slot { get; set; } = "";
            public string SourceArchiveRelPath { get; set; } = "";
            public string OutputPrefix { get; set; } = "";
            public int Ds1ParamRowId { get; set; }
        }

        public static readonly Dictionary<string, List<ArmorPieceSpec>> KnownSets = new(StringComparer.OrdinalIgnoreCase)
        {
            ["black_knight"] = new()
            {
                new ArmorPieceSpec { Slot = "head", SourceArchiveRelPath = "parts/hd_a_9490.partsbnd.dcx", OutputPrefix = "hd", Ds1ParamRowId = 320000 },
                new ArmorPieceSpec { Slot = "body", SourceArchiveRelPath = "parts/bd_a_9490.partsbnd.dcx", OutputPrefix = "bd", Ds1ParamRowId = 321000 },
                new ArmorPieceSpec { Slot = "arms", SourceArchiveRelPath = "parts/am_a_9490.partsbnd.dcx", OutputPrefix = "am", Ds1ParamRowId = 322000 },
                new ArmorPieceSpec { Slot = "legs_m", SourceArchiveRelPath = "parts/lg_m_9490.partsbnd.dcx", OutputPrefix = "lg_m", Ds1ParamRowId = 323000 },
                new ArmorPieceSpec { Slot = "legs_f", SourceArchiveRelPath = "parts/lg_f_9490.partsbnd.dcx", OutputPrefix = "lg_f", Ds1ParamRowId = 323000 },
            }
        };

        public static int ExecutePortSoulsSet(Dictionary<string, string> options)
        {
            string setKey = options.TryGetValue("set", out string? sk) && !string.IsNullOrEmpty(sk) ? sk.ToLowerInvariant() : "black_knight";
            if (!KnownSets.TryGetValue(setKey, out var pieces))
            {
                Console.Error.WriteLine($"[SoulsPort ERROR] Unknown legacy set: '{setKey}'. Available: {string.Join(", ", KnownSets.Keys)}");
                return 1;
            }

            string gameDir = options.TryGetValue("game-dir", out string? gd) && !string.IsNullOrEmpty(gd)
                ? gd
                : ResolveDefaultDs1Dir();

            if (string.IsNullOrEmpty(gameDir) || !Directory.Exists(gameDir))
            {
                Console.Error.WriteLine($"[SoulsPort ERROR] Dark Souls 1 DATA directory not found. Please provide --game-dir.");
                return 1;
            }

            string outputDir = options.TryGetValue("output-dir", out string? od) && !string.IsNullOrEmpty(od)
                ? od
                : Path.Combine("input_mods", "BlackKnightSet");

            string targetModelId = options.TryGetValue("target-model-id", out string? tmid) && !string.IsNullOrEmpty(tmid)
                ? tmid
                : "9490";

            Directory.CreateDirectory(outputDir);
            Console.WriteLine($"[SoulsPort] Initializing extraction for '{setKey}' from: {gameDir}");
            Console.WriteLine($"[SoulsPort] Target model ID: {targetModelId}, Output: {outputDir}");

            using var reader = new Ds1ArchiveReader(gameDir);

            // 1. Extract FMG text & descriptions
            var (names, descriptions) = ExtractDs1Texts(reader);

            // 2. Extract DS1 EquipParamProtector stats
            var paramStats = ExtractDs1Stats(reader, pieces.Select(p => p.Ds1ParamRowId).Distinct());

            var manifestPieces = new List<Dictionary<string, object>>();

            // 3. Process each armor piece
            foreach (var piece in pieces)
            {
                Console.WriteLine($"[SoulsPort] Processing {piece.Slot} from {piece.SourceArchiveRelPath}...");
                var bnd3 = reader.ReadBnd3(piece.SourceArchiveRelPath);
                if (bnd3 == null)
                {
                    Console.WriteLine($"[SoulsPort WARN] Could not read {piece.SourceArchiveRelPath}");
                    continue;
                }

                var flverFile = bnd3.Files.FirstOrDefault(f => f.Name.EndsWith(".flver", StringComparison.OrdinalIgnoreCase));
                var tpfFile = bnd3.Files.FirstOrDefault(f => f.Name.EndsWith(".tpf", StringComparison.OrdinalIgnoreCase));

                if (flverFile == null)
                {
                    Console.WriteLine($"[SoulsPort WARN] No FLVER found in {piece.SourceArchiveRelPath}");
                    continue;
                }

                byte[] modernizedFlver = FlverModernizer.ModernizeFlver(flverFile.Bytes);

                // Determine gender outputs
                List<string> outputGenders = piece.OutputPrefix.StartsWith("lg_m") ? new() { "m" }
                    : piece.OutputPrefix.StartsWith("lg_f") ? new() { "f" }
                    : new() { "m", "f" };

                string baseSlot = piece.OutputPrefix.Split('_')[0];

                foreach (var gender in outputGenders)
                {
                    string fileName = $"{baseSlot}_{gender}_{targetModelId}.partsbnd.dcx";
                    string targetFilePath = Path.Combine(outputDir, fileName);

                    string virtualFlver = $@"N:\GR\data\INTERROOT_win64\parts\{GetSlotFolderName(baseSlot)}\{baseSlot.ToUpper()}_{gender.ToUpper()}_{targetModelId}\{baseSlot.ToUpper()}_{gender.ToUpper()}_{targetModelId}.flver";
                    string virtualTpf = $@"N:\GR\data\INTERROOT_win64\parts\{GetSlotFolderName(baseSlot)}\{baseSlot.ToUpper()}_{gender.ToUpper()}_{targetModelId}\{baseSlot.ToUpper()}_{gender.ToUpper()}_{targetModelId}.tpf";

                    FlverModernizer.PackagePartsBnd(targetFilePath, virtualFlver, modernizedFlver, virtualTpf, tpfFile?.Bytes);
                    Console.WriteLine($"[SoulsPort SUCCESS] Wrote Elden Ring parts archive: {fileName}");

                    names.TryGetValue(piece.Ds1ParamRowId, out string? pieceName);
                    descriptions.TryGetValue(piece.Ds1ParamRowId, out string? pieceDesc);
                    paramStats.TryGetValue(piece.Ds1ParamRowId, out var stats);

                    manifestPieces.Add(new Dictionary<string, object>
                    {
                        ["slot"] = baseSlot,
                        ["gender"] = gender,
                        ["fileName"] = fileName,
                        ["filePath"] = targetFilePath,
                        ["modelId"] = targetModelId,
                        ["sourceRowId"] = piece.Ds1ParamRowId,
                        ["name"] = pieceName ?? $"Black Knight {baseSlot}",
                        ["description"] = (pieceDesc ?? "").Trim(),
                        ["stats"] = stats ?? new Dictionary<string, object>()
                    });
                }
            }

            // 4. Write metadata JSON
            string metaPath = options.TryGetValue("export-meta", out string? em) && !string.IsNullOrEmpty(em)
                ? em
                : Path.Combine(outputDir, "souls_port_meta.json");

            var metaRoot = new Dictionary<string, object>
            {
                ["setKey"] = setKey,
                ["setName"] = "Black Knight Set",
                ["sourceGame"] = "Dark Souls 1",
                ["targetModelId"] = targetModelId,
                ["exportedAt"] = DateTime.UtcNow.ToString("o"),
                ["pieces"] = manifestPieces
            };

            File.WriteAllText(metaPath, JsonSerializer.Serialize(metaRoot, new JsonSerializerOptions { WriteIndented = true }));
            Console.WriteLine($"[SoulsPort SUCCESS] Exported port metadata to: {metaPath}");
            return 0;
        }

        private static string GetSlotFolderName(string prefix) => prefix.ToLowerInvariant() switch
        {
            "hd" => "Head",
            "bd" => "FullBody",
            "am" => "Arm",
            "lg" => "Leg",
            _ => "FullBody"
        };

        private static (Dictionary<int, string> Names, Dictionary<int, string> Descriptions) ExtractDs1Texts(Ds1ArchiveReader reader)
        {
            var names = new Dictionary<int, string>();
            var descs = new Dictionary<int, string>();
            var msgBnd = reader.ReadBnd3("msg/ENGLISH/item.msgbnd.dcx");
            if (msgBnd == null) return (names, descs);

            foreach (var f in msgBnd.Files)
            {
                string fn = f.Name ?? "";
                if (fn.Contains("防具名") || fn.Contains("ArmorNames") || fn.Contains("ProtectorName"))
                {
                    var fmg = FMG.Read(f.Bytes);
                    foreach (var e in fmg.Entries) if (e.Text != null) names[e.ID] = e.Text;
                }
                else if (fn.Contains("防具うんちく") || fn.Contains("ArmorDescriptions") || fn.Contains("ProtectorCaption"))
                {
                    var fmg = FMG.Read(f.Bytes);
                    foreach (var e in fmg.Entries) if (e.Text != null) descs[e.ID] = e.Text;
                }
            }
            return (names, descs);
        }

        private static Dictionary<int, Dictionary<string, object>> ExtractDs1Stats(Ds1ArchiveReader reader, IEnumerable<int> rowIds)
        {
            var result = new Dictionary<int, Dictionary<string, object>>();
            var paramBnd = reader.ReadBnd3("param/GameParam/GameParam.parambnd.dcx");
            if (paramBnd == null) return result;

            var protFile = paramBnd.Files.FirstOrDefault(f => f.Name.EndsWith("EquipParamProtector.param", StringComparison.OrdinalIgnoreCase));
            if (protFile == null) return result;

            var param = PARAM.Read(protFile.Bytes);
            string defPath = @"tools\vendor\Paramdex\DS1\Defs\EquipParamProtector.xml";
            if (File.Exists(defPath))
            {
                var def = PARAMDEF.XmlDeserialize(defPath);
                param.ApplyParamdef(def);
            }

            var targetSet = new HashSet<int>(rowIds);
            foreach (var r in param.Rows)
            {
                if (targetSet.Contains(r.ID))
                {
                    var d = new Dictionary<string, object>();
                    foreach (var c in r.Cells) d[c.Def.InternalName] = c.Value;
                    result[r.ID] = d;
                }
            }
            return result;
        }

        private static string ResolveDefaultDs1Dir()
        {
            string[] candidates = [
                @"D:\SteamLibrary\steamapps\common\Dark Souls Prepare to Die Edition\DATA",
                @"C:\Program Files (x86)\Steam\steamapps\common\Dark Souls Prepare to Die Edition\DATA",
                @"C:\Games\Dark Souls Remastered",
                @"D:\Games\Dark Souls Remastered"
            ];
            return candidates.FirstOrDefault(Directory.Exists) ?? "";
        }
    }
}
