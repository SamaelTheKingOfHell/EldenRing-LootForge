using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace TestDs1Extract
{
    class Program
    {
        static void EnsureOodleLoaded()
        {
            if (SoulsFormats.Oodle.Oodle6Ptr != IntPtr.Zero || SoulsFormats.Oodle.Oodle8Ptr != IntPtr.Zero || SoulsFormats.Oodle.Oodle9Ptr != IntPtr.Zero)
                return;

            string[] searchDirs = [
                @"D:\SteamLibrary\steamapps\common\ELDEN RING\Game",
                AppContext.BaseDirectory,
                Path.Combine(AppContext.BaseDirectory, "..", "..", ".."),
                Directory.GetCurrentDirectory()
            ];

            string[] oodleDlls = ["oo2core_6_win64.dll", "oo2core_8_win64.dll", "oo2core_9_win64.dll"];

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
                                Console.WriteLine($"Loaded Oodle from: {fullPath}");
                                return;
                            }
                        }
                        catch { }
                    }
                }
            }
        }

        static void Main(string[] args)
        {
            EnsureOodleLoaded();

            string dataDir = @"D:\SteamLibrary\steamapps\common\Dark Souls Prepare to Die Edition\DATA";
            string bhdPath = Path.Combine(dataDir, "dvdbnd1.bhd5");
            string bdtPath = Path.Combine(dataDir, "dvdbnd1.bdt");

            var bhd = BHD5.Read(bhdPath, BHD5.Game.DarkSouls1);
            var allHashes = bhd.Buckets.SelectMany(b => b).ToDictionary(h => h.FileNameHash);
            uint ds1Hash = HashHelper.FromPathHash("parts/hd_a_9490.partsbnd.dcx");

            using var fs = File.OpenRead(bdtPath);
            fs.Seek(allHashes[ds1Hash].FileOffset, SeekOrigin.Begin);
            byte[] ds1Dcx = new byte[allHashes[ds1Hash].PaddedFileSize];
            fs.ReadExactly(ds1Dcx, 0, ds1Dcx.Length);
            var ds1Bnd = BND3.Read(DCX.Decompress(ds1Dcx));
            var flverFile = ds1Bnd.Files.First(f => f.Name.EndsWith(".flver"));
            var flver = FLVER2.Read(flverFile.Bytes);

            Console.WriteLine($"Original DS1 FLVER: Version 0x{flver.Header.Version:X}, Meshes: {flver.Meshes.Count}");

            // Upgrade Header to Elden Ring (0x20014)
            flver.Header.Version = 0x20014;
            flver.Header.Unicode = true;

            // Construct standard Elden Ring Rigged Armor Layout (40 bytes)
            var erLayout = new FLVER2.BufferLayout
            {
                new FLVER.LayoutMember(FLVER.LayoutType.Float3, FLVER.LayoutSemantic.Position, 0),
                new FLVER.LayoutMember(FLVER.LayoutType.UByte4, FLVER.LayoutSemantic.Normal, 0),
                new FLVER.LayoutMember(FLVER.LayoutType.UByte4, FLVER.LayoutSemantic.Tangent, 0),
                new FLVER.LayoutMember(FLVER.LayoutType.UByte4, FLVER.LayoutSemantic.BoneIndices, 0),
                new FLVER.LayoutMember(FLVER.LayoutType.UByte4Norm, FLVER.LayoutSemantic.BoneWeights, 0),
                new FLVER.LayoutMember(FLVER.LayoutType.UByte4Norm, FLVER.LayoutSemantic.VertexColor, 1),
                new FLVER.LayoutMember(FLVER.LayoutType.Short4, FLVER.LayoutSemantic.UV, 0),
            };

            flver.BufferLayouts.Clear();
            flver.BufferLayouts.Add(erLayout);

            foreach (var mesh in flver.Meshes)
            {
                mesh.VertexBuffers.Clear();
                mesh.VertexBuffers.Add(new FLVER2.VertexBuffer(0));

                foreach (var v in mesh.Vertices)
                {
                    while (v.UVs.Count < 2) v.UVs.Add(Vector3.Zero);
                    while (v.Colors.Count < 2) v.Colors.Add(new FLVER.VertexColor(1f, 1f, 1f, 1f));
                }
            }

            // Material and texture modernization
            foreach (var mat in flver.Materials)
            {
                mat.MTD = "M[ARSN]_e.matbin";
                var oldTexs = mat.Textures.ToList();
                mat.Textures.Clear();

                foreach (var t in oldTexs)
                {
                    string p = t.ParamName.ToLowerInvariant();
                    if (p.Contains("diffuse") || p.Contains("albedo") || p.Contains("color"))
                    {
                        mat.Textures.Add(new FLVER2.Texture { ParamName = "C_AMSN__snp_Texture2D_2_AlbedoMap_0", Path = Path.GetFileNameWithoutExtension(t.Path) + "_a.tif" });
                    }
                    else if (p.Contains("specular") || p.Contains("metallic") || p.Contains("refl"))
                    {
                        mat.Textures.Add(new FLVER2.Texture { ParamName = "C_AMSN__snp_Texture2D_0_MetallicMap_0", Path = Path.GetFileNameWithoutExtension(t.Path) + "_m.tif" });
                    }
                    else if (p.Contains("bump") || p.Contains("normal"))
                    {
                        mat.Textures.Add(new FLVER2.Texture { ParamName = "C_AMSN__snp_Texture2D_7_NormalMap_4", Path = Path.GetFileNameWithoutExtension(t.Path) + "_n.tif" });
                    }
                }
            }

            byte[] convertedFlverBytes = flver.Write();
            Console.WriteLine($"Successfully wrote converted FLVER2: {convertedFlverBytes.Length} bytes!");

            var erBnd = new BND4
            {
                BigEndian = false,
                Compression = new DCX.DcxKrakCompressionInfo(DCX.KrakCompressionPreset.EldenRing),
                Unicode = true,
                Format = Binder.Format.IDs | Binder.Format.Names1 | Binder.Format.Compression
            };

            erBnd.Files.Add(new BinderFile(Binder.FileFlags.Flag1, 200, @"N:\GR\data\INTERROOT_win64\parts\Head\HD_M_9490\HD_M_9490.flver", convertedFlverBytes));

            var tpfFile = ds1Bnd.Files.FirstOrDefault(f => f.Name.EndsWith(".tpf"));
            if (tpfFile != null)
            {
                var tpf = TPF.Read(tpfFile.Bytes);
                tpf.Platform = TPF.TPFPlatform.PC;
                byte[] tpfBytes = tpf.Write();
                erBnd.Files.Add(new BinderFile(Binder.FileFlags.Flag1, 100, @"N:\GR\data\INTERROOT_win64\parts\Head\HD_M_9490\HD_M_9490.tpf", tpfBytes));
            }

            string testOutPath = Path.Combine(AppContext.BaseDirectory, "hd_m_9490.partsbnd.dcx");
            erBnd.Write(testOutPath);
            Console.WriteLine($"SUCCESS! Wrote Elden Ring partsbnd to: {testOutPath} (size: {new FileInfo(testOutPath).Length} bytes)!");

            // Test reading back the written BND4 with DCX_KRAK
            var readBack = BND4.Read(testOutPath);
            Console.WriteLine($"SUCCESS! Read back BND4 with {readBack.Files.Count} files, Compression: {readBack.Compression.Type}!");
        }
    }
}
