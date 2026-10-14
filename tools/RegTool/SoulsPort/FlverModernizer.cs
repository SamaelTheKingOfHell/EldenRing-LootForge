using System;
using System.IO;
using System.Linq;
using System.Numerics;
using SoulsFormats;

namespace LootForge.RegTool.SoulsPort
{
    /// <summary>
    /// Modernizes legacy FromSoftware FLVER2 models (v0x2000C) into Elden Ring FLVER2 (v0x20014)
    /// with DirectX 12 PBR vertex layouts, shader re-targeting, and Oodle Kraken packaging.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class FlverModernizer
    {
        public static readonly FLVER2.BufferLayout EldenRingArmorLayout = new()
        {
            new FLVER.LayoutMember(FLVER.LayoutType.Float3, FLVER.LayoutSemantic.Position, 0),
            new FLVER.LayoutMember(FLVER.LayoutType.UByte4, FLVER.LayoutSemantic.Normal, 0),
            new FLVER.LayoutMember(FLVER.LayoutType.UByte4, FLVER.LayoutSemantic.Tangent, 0),
            new FLVER.LayoutMember(FLVER.LayoutType.UByte4, FLVER.LayoutSemantic.BoneIndices, 0),
            new FLVER.LayoutMember(FLVER.LayoutType.UByte4Norm, FLVER.LayoutSemantic.BoneWeights, 0),
            new FLVER.LayoutMember(FLVER.LayoutType.UByte4Norm, FLVER.LayoutSemantic.VertexColor, 1),
            new FLVER.LayoutMember(FLVER.LayoutType.Short4, FLVER.LayoutSemantic.UV, 0),
        };

        /// <summary>
        /// Modernizes a DS1 FLVER model into an Elden Ring compatible FLVER2.
        /// </summary>
        public static byte[] ModernizeFlver(byte[] flverBytes)
        {
            var flver = FLVER2.Read(flverBytes);

            // 1. Upgrade Header to Elden Ring
            flver.Header.Version = 0x20014;
            flver.Header.Unicode = true;

            // 2. Apply Elden Ring 40-byte vertex buffer layout
            flver.BufferLayouts.Clear();
            flver.BufferLayouts.Add(EldenRingArmorLayout);

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

            // 3. Modernize materials and texture sampler bindings to Elden Ring PBR
            foreach (var mat in flver.Materials)
            {
                mat.MTD = "M[ARSN]_e.matbin";
                var oldTextures = mat.Textures.ToList();
                mat.Textures.Clear();

                foreach (var t in oldTextures)
                {
                    string p = (t.ParamName ?? "").ToLowerInvariant();
                    string baseName = Path.GetFileNameWithoutExtension(t.Path ?? "");

                    if (p.Contains("diffuse") || p.Contains("albedo") || p.Contains("color"))
                    {
                        mat.Textures.Add(new FLVER2.Texture
                        {
                            ParamName = "C_AMSN__snp_Texture2D_2_AlbedoMap_0",
                            Path = baseName + "_a.tif"
                        });
                    }
                    else if (p.Contains("specular") || p.Contains("metallic") || p.Contains("refl"))
                    {
                        mat.Textures.Add(new FLVER2.Texture
                        {
                            ParamName = "C_AMSN__snp_Texture2D_0_MetallicMap_0",
                            Path = baseName + "_m.tif"
                        });
                    }
                    else if (p.Contains("bump") || p.Contains("normal"))
                    {
                        mat.Textures.Add(new FLVER2.Texture
                        {
                            ParamName = "C_AMSN__snp_Texture2D_7_NormalMap_4",
                            Path = baseName + "_n.tif"
                        });
                    }
                }
            }

            return flver.Write();
        }

        /// <summary>
        /// Packages modernized FLVER2 and TPF assets into an Elden Ring BND4 container with Oodle Kraken compression.
        /// </summary>
        public static void PackagePartsBnd(
            string outputPath,
            string virtualFlverPath,
            byte[] modernizedFlverBytes,
            string virtualTpfPath,
            byte[]? tpfBytes)
        {
            var erBnd = new BND4
            {
                BigEndian = false,
                Compression = new DCX.DcxKrakCompressionInfo(DCX.KrakCompressionPreset.EldenRing),
                Unicode = true,
                Format = Binder.Format.IDs | Binder.Format.Names1 | Binder.Format.Compression
            };

            erBnd.Files.Add(new BinderFile(Binder.FileFlags.Flag1, 200, virtualFlverPath, modernizedFlverBytes));

            if (tpfBytes != null && tpfBytes.Length > 0)
            {
                var tpf = TPF.Read(tpfBytes);
                tpf.Platform = TPF.TPFPlatform.PC;
                byte[] repackTpf = tpf.Write();
                erBnd.Files.Add(new BinderFile(Binder.FileFlags.Flag1, 100, virtualTpfPath, repackTpf));
            }

            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            erBnd.Write(outputPath);
        }
    }
}
