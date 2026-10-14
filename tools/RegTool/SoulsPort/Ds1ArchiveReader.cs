using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool.SoulsPort
{
    /// <summary>
    /// Random-access in-memory reader for Dark Souls 1 (PTDE) BHD5/BDT archive pairs.
    /// Enables high-performance selective extraction without full game unpacking.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public class Ds1ArchiveReader : IDisposable
    {
        private readonly string _dataDir;
        private readonly Dictionary<string, (BHD5 Bhd, FileStream BdtStream, Dictionary<ulong, BHD5.FileHeader> Headers)> _archives = new();

        public Ds1ArchiveReader(string dataDir)
        {
            _dataDir = dataDir ?? throw new ArgumentNullException(nameof(dataDir));
            LoadArchives();
        }

        private void LoadArchives()
        {
            for (int i = 0; i <= 3; i++)
            {
                string name = $"dvdbnd{i}";
                string bhdPath = Path.Combine(_dataDir, $"{name}.bhd5");
                string bdtPath = Path.Combine(_dataDir, $"{name}.bdt");

                if (!File.Exists(bhdPath) || !File.Exists(bdtPath))
                    continue;

                try
                {
                    var bhd = BHD5.Read(bhdPath, BHD5.Game.DarkSouls1);
                    var bdtStream = File.OpenRead(bdtPath);
                    var headerDict = new Dictionary<ulong, BHD5.FileHeader>();

                    foreach (var bucket in bhd.Buckets)
                    {
                        foreach (var header in bucket)
                        {
                            headerDict[header.FileNameHash] = header;
                        }
                    }

                    _archives[name] = (bhd, bdtStream, headerDict);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[SoulsPort WARN] Could not open {name}: {ex.Message}");
                }
            }
        }

        /// <summary>
        /// Reads raw bytes for a file matching the relative archive path across all loaded dvdbnd archives.
        /// Automatically handles FromSoftware path hashing.
        /// </summary>
        public byte[]? ReadFile(string relativePath)
        {
            uint hash = HashHelper.FromPathHash(relativePath);

            foreach (var kvp in _archives)
            {
                var (_, bdtStream, headers) = kvp.Value;
                if (headers.TryGetValue(hash, out var header))
                {
                    lock (bdtStream)
                    {
                        bdtStream.Seek(header.FileOffset, SeekOrigin.Begin);
                        byte[] rawBytes = new byte[header.PaddedFileSize];
                        bdtStream.ReadExactly(rawBytes, 0, rawBytes.Length);

                        // Decompress DCX if wrapped
                        if (DCX.Is(rawBytes))
                        {
                            return DCX.Decompress(rawBytes);
                        }

                        return rawBytes;
                    }
                }
            }

            return null;
        }

        /// <summary>
        /// Reads and parses a BND3 container from the given archive path.
        /// </summary>
        public BND3? ReadBnd3(string relativePath)
        {
            byte[]? bytes = ReadFile(relativePath);
            if (bytes == null) return null;
            return BND3.Read(bytes);
        }

        public void Dispose()
        {
            foreach (var kvp in _archives)
            {
                kvp.Value.BdtStream.Dispose();
            }
            _archives.Clear();
        }
    }
}
