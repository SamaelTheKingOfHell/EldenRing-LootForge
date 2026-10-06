using System;
using System.IO;
using System.Linq;
using SoulsFormats;

namespace ExtractMsgFiles
{
    class Program
    {
        static int Main(string[] args)
        {
            if (args.Length < 2)
            {
                Console.WriteLine("Usage: ExtractMsgFiles <game_dir> <output_dir>");
                Console.WriteLine("Example: ExtractMsgFiles \"C:\\Games\\ELDEN RING\\Game\" \"backups/msg\"");
                return 1;
            }

            string gameDir = args[0];
            string outputDir = args[1];

            string bhd5Path = Path.Combine(gameDir, "Data0.bhd5");
            string bdtPath = Path.Combine(gameDir, "Data0.bdt");

            if (!File.Exists(bhd5Path))
            {
                Console.WriteLine($"[ERROR] Data0.bhd5 not found at: {bhd5Path}");
                return 1;
            }

            if (!File.Exists(bdtPath))
            {
                Console.WriteLine($"[ERROR] Data0.bdt not found at: {bdtPath}");
                return 1;
            }

            try
            {
                Console.WriteLine($"[ExtractMsgFiles] Loading BHD5 header: {bhd5Path}");
                BHD5 bhd = BHD5.Read(bhd5Path, BHD5.Game.EldenRing);

                Console.WriteLine($"[ExtractMsgFiles] Opening BDT data: {bdtPath}");
                using FileStream bdtStream = File.OpenRead(bdtPath);

                int extracted = 0;

                // Extract all msg files from engUS locale
                foreach (var bucket in bhd.Buckets)
                {
                    foreach (var fileHeader in bucket)
                    {
                        // Filter for msg/engUS/*.msgbnd.dcx files
                        // Note: Files are stored with hashed names, so we need to check a known hash
                        // or extract everything and filter by size/magic bytes

                        // For now, extract common msg files by trying known paths
                        // We'll extract item.msgbnd.dcx specifically
                        
                        try
                        {
                            byte[] fileData = fileHeader.ReadFile(bdtStream);
                            
                            // Check if this is a msgbnd.dcx file (starts with DCX magic)
                            if (fileData.Length > 4 && fileData[0] == 'D' && fileData[1] == 'C' && fileData[2] == 'X')
                            {
                                // Try to read as BND4
                                BND4 bnd = BND4.Read(fileData);
                                
                                // Check if it contains .fmg files (message files)
                                var hasFmgFiles = bnd.Files.Any(f => f.Name != null && f.Name.EndsWith(".fmg", StringComparison.OrdinalIgnoreCase));
                                
                                if (hasFmgFiles)
                                {
                                    // Check which type of msg file this is by looking at FMG names
                                    var firstFmgName = bnd.Files.FirstOrDefault(f => f.Name != null && f.Name.EndsWith(".fmg"))?.Name;
                                    
                                    string outputFileName = "unknown.msgbnd.dcx";
                                    
                                    if (firstFmgName != null)
                                    {
                                        if (firstFmgName.Contains("Weapon", StringComparison.OrdinalIgnoreCase) || 
                                            firstFmgName.Contains("Protector", StringComparison.OrdinalIgnoreCase) ||
                                            firstFmgName.Contains("Accessory", StringComparison.OrdinalIgnoreCase) ||
                                            firstFmgName.Contains("Goods", StringComparison.OrdinalIgnoreCase))
                                        {
                                            outputFileName = "item.msgbnd.dcx";
                                        }
                                        else if (firstFmgName.Contains("Menu", StringComparison.OrdinalIgnoreCase))
                                        {
                                            outputFileName = "menu.msgbnd.dcx";
                                        }
                                        else if (firstFmgName.Contains("Event", StringComparison.OrdinalIgnoreCase))
                                        {
                                            outputFileName = "event.msgbnd.dcx";
                                        }
                                    }
                                    
                                    // Only extract item.msgbnd.dcx for now
                                    if (outputFileName == "item.msgbnd.dcx")
                                    {
                                        string engUSDir = Path.Combine(outputDir, "engUS");
                                        Directory.CreateDirectory(engUSDir);
                                        
                                        string outputPath = Path.Combine(engUSDir, outputFileName);
                                        File.WriteAllBytes(outputPath, fileData);
                                        
                                        Console.WriteLine($"[ExtractMsgFiles] Extracted: {outputFileName} ({fileData.Length} bytes)");
                                        Console.WriteLine($"[ExtractMsgFiles]   Contains {bnd.Files.Count} FMG files:");
                                        foreach (var fmgFile in bnd.Files.Where(f => f.Name != null && f.Name.EndsWith(".fmg")).Take(5))
                                        {
                                            Console.WriteLine($"[ExtractMsgFiles]     - {Path.GetFileName(fmgFile.Name)}");
                                        }
                                        
                                        extracted++;
                                        
                                        // Stop after finding item.msgbnd.dcx
                                        if (extracted > 0)
                                            break;
                                    }
                                }
                            }
                        }
                        catch
                        {
                            // Skip files that can't be read as BND4
                            continue;
                        }
                    }
                    
                    if (extracted > 0)
                        break;
                }

                if (extracted == 0)
                {
                    Console.WriteLine("[ExtractMsgFiles WARN] Could not find item.msgbnd.dcx in Data0.bdt");
                    Console.WriteLine("[ExtractMsgFiles] Note: This tool extracts from the packed game files.");
                    return 1;
                }

                Console.WriteLine($"[ExtractMsgFiles SUCCESS] Extracted {extracted} msg file(s) to: {outputDir}");
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ExtractMsgFiles ERROR] {ex.Message}");
                Console.WriteLine(ex.StackTrace);
                return 1;
            }
        }
    }
}
