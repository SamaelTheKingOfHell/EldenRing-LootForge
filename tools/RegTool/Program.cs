using System;
using System.Collections.Generic;
using System.Linq;

namespace LootForge.RegTool
{
    /// <summary>
    /// RegTool Command Line Interface entry point.
    /// Parses CLI arguments and delegates execution to specialized modular services.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    class Program
    {
        static int Main(string[] args)
        {
            EnsureOodleLoaded();

            if (args.Length == 0 || args[0] == "--help" || args[0] == "-h")
            {
                PrintUsage();
                return 0;
            }

            string command = args[0].ToLowerInvariant();
            var options = ParseArguments(args.Skip(1).ToArray());

            try
            {
                switch (command)
                {
                    case "patch":
                        return PatchService.ExecutePatch(options);
                    case "verify":
                        return DiagnosticService.ExecuteVerify(options);
                    case "extract-msg":
                        return DiagnosticService.ExtractMsgFiles(options);
                    case "dump-fmg":
                        return DiagnosticService.ExecuteDumpFmg(options);
                    case "dump-reg":
                        return DiagnosticService.ExecuteDumpReg(options);
                    case "dump-tpf":
                        return TpfService.ExecuteDumpTpf(options);
                    case "add-shop-item":
                        return ShopService.ExecuteAddShopItem(options);
                    case "find-item":
                        return DiagnosticService.ExecuteFindItem(options);
                    case "dump-boss-lots":
                        return DiagnosticService.ExecuteDumpBossLots(options);
                    case "dump-emevd":
                        return DiagnosticService.ExecuteDumpEmevd(options);
                    case "find-multi-lots":
                        return DiagnosticService.ExecuteFindMultiSlotLots(options);
                    case "inject-boss-loot-pools":
                        return BossLootPoolService.ExecuteInjectBossLootPools(options);
                    case "introspect-world":
                        return SmartDiscoveryService.ExecuteIntrospect(options);
                    case "sweep-vanilla":
                        return UniversalSweeperService.ExecuteSweep(options);
                    case "extract-skills-movesets":
                        return SkillMovesetService.ExecuteExtractSkillsMovesets(options);
                    default:
                        Console.Error.WriteLine($"Unknown command: '{command}'");
                        PrintUsage();
                        return 1;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[RegTool ERROR] {ex.Message}");
                Console.Error.WriteLine(ex.StackTrace);
                return 2;
            }
        }

        static void PrintUsage()
        {
            Console.WriteLine("LootForge Regulation Tool (RegTool)");
            Console.WriteLine("Usage:");
            Console.WriteLine("  RegTool patch --input <source_reg> --output <target_reg> --defs <paramdex_defs> --spec <patch_spec.json> [--msg <game_msg_engUS_dir>]");
            Console.WriteLine("  RegTool verify --input <regulation.bin>");
            Console.WriteLine("  RegTool extract-msg --game-dir <elden_ring_game_dir> --output <backup_msg_dir>");
            Console.WriteLine("  RegTool dump-fmg --input <item.msgbnd.dcx> [--search <query>]");
            Console.WriteLine("  RegTool dump-reg --input <regulation.bin> [--defs <paramdex_defs>]");
            Console.WriteLine("  RegTool extract-skills-movesets --input <mod_regulation.bin> [--defs <defs>] [--output <out.json>] [--msg <msg_dir>]");
        }

        static void EnsureOodleLoaded()
        {
            if (SoulsFormats.Oodle.Oodle6Ptr != IntPtr.Zero || SoulsFormats.Oodle.Oodle8Ptr != IntPtr.Zero || SoulsFormats.Oodle.Oodle9Ptr != IntPtr.Zero)
                return;

            string[] searchDirs = [
                AppContext.BaseDirectory,
                Path.Combine(AppContext.BaseDirectory, "..", "..", ".."),
                Directory.GetCurrentDirectory()
            ];

            string[] oodleDlls = ["oo2core_9_win64.dll", "oo2core_8_win64.dll", "oo2core_6_win64.dll"];

            foreach (var dir in searchDirs)
            {
                if (!Directory.Exists(dir)) continue;
                foreach (var dll in oodleDlls)
                {
                    string fullPath = Path.Combine(dir, dll);
                    if (File.Exists(fullPath))
                    {
                        try
                        {
                            IntPtr ptr = System.Runtime.InteropServices.NativeLibrary.Load(fullPath);
                            if (ptr != IntPtr.Zero)
                            {
                                if (dll.Contains("_9_")) SoulsFormats.Oodle.Oodle9Ptr = ptr;
                                else if (dll.Contains("_8_")) SoulsFormats.Oodle.Oodle8Ptr = ptr;
                                else if (dll.Contains("_6_")) SoulsFormats.Oodle.Oodle6Ptr = ptr;
                                return;
                            }
                        }
                        catch { }
                    }
                }
            }
        }

        static Dictionary<string, string> ParseArguments(string[] args)
        {
            var dict = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i].StartsWith("--") && i + 1 < args.Length && !args[i + 1].StartsWith("--"))
                {
                    string key = args[i].Substring(2).ToLowerInvariant();
                    dict[key] = args[i + 1];
                    i++;
                }
                else if (args[i].StartsWith("--"))
                {
                    string key = args[i].Substring(2).ToLowerInvariant();
                    dict[key] = "true";
                }
            }
            return dict;
        }
    }
}
