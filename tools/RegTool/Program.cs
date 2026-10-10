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
            }
            return dict;
        }
    }
}
