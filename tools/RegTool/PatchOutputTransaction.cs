namespace LootForge.RegTool;

/// <summary>Stage regulation and messages together, retaining previous output on failure.</summary>
public sealed class PatchOutputTransaction : IDisposable
{
    private readonly string destination;
    private readonly string staging;
    /// <summary>Regulation path passed to serializers and FMG output routing.</summary>
    public string RegulationPath { get; }

    /// <summary>Create private staging beside the selected regulation.</summary>
    public PatchOutputTransaction(string outputPath)
    {
        destination = Path.GetDirectoryName(Path.GetFullPath(outputPath))!;
        Directory.CreateDirectory(destination);
        staging = Path.Combine(destination, ".lootforge-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(staging);
        RegulationPath = Path.Combine(staging, Path.GetFileName(outputPath));
    }

    /// <summary>Publish completed files, restoring originals if replacement fails.</summary>
    public void Commit()
    {
        var files = Directory.GetFiles(staging, "*", SearchOption.AllDirectories);
        var installed = new List<(string Target, string? Backup)>();
        try
        {
            foreach (var file in files)
            {
                string relative = Path.GetRelativePath(staging, file);
                string target = Path.Combine(destination, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                string? backup = null;
                if (File.Exists(target))
                {
                    backup = Path.Combine(staging, "previous", relative);
                    Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
                    File.Copy(target, backup);
                }
                installed.Add((target, backup));
                File.Move(file, target, true);
            }
        }
        catch
        {
            foreach (var (target, backup) in installed.AsEnumerable().Reverse())
            {
                if (backup != null) File.Move(backup, target, true);
                else File.Delete(target);
            }
            throw;
        }
    }

    /// <summary>Discard staging data after success or failure.</summary>
    public void Dispose() => Directory.Delete(staging, true);
}
