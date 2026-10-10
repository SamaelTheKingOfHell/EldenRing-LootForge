using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Service for inspecting and dumping textures from TPF and TPF.DCX containers.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class TpfService
    {
        public static int ExecuteDumpTpf(Dictionary<string, string> options)
        {
            if (!options.TryGetValue("input", out string? inputPath) || string.IsNullOrEmpty(inputPath))
            {
                Console.Error.WriteLine("Missing required --input path to .tpf or .tpf.dcx file.");
                return 1;
            }

            if (!File.Exists(inputPath))
            {
                Console.Error.WriteLine($"File not found: {inputPath}");
                return 1;
            }

            Console.WriteLine($"[RegTool] Reading TPF container: {inputPath}...");
            TPF tpf = TPF.Read(inputPath);
            Console.WriteLine($"[RegTool] TPF contains {tpf.Textures.Count} textures. Platform: {tpf.Platform}.");

            string searchQuery = options.TryGetValue("search", out string? sq) ? sq : "";
            var matches = string.IsNullOrEmpty(searchQuery)
                ? tpf.Textures
                : tpf.Textures.Where(t => t.Name.Contains(searchQuery, StringComparison.OrdinalIgnoreCase)).ToList();

            Console.WriteLine($"[RegTool] Matches for '{searchQuery}': {matches.Count}");
            foreach (var tex in matches.Take(50))
            {
                Console.WriteLine($"  Texture: {tex.Name} (format: {tex.Format}, size: {tex.Bytes.Length} bytes)");
            }

            return 0;
        }
    }
}
