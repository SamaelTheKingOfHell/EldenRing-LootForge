using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Patch each installed item-text language and DLC archive while preserving its original content.</summary>
public static class MessageArchiveService
{
    /// <summary>Read a language directory or message root and retain every source language in the output.</summary>
    public static int Inject(string source, string regulationOutput, List<FmgInjector.FmgTextSpec> specs, Action<BND4>? transform,
        Action<BND4>? prepare = null, Action<BND4, string>? beforeArchive = null, Action<BND4, string>? afterArchive = null)
    {
        string full = Path.GetFullPath(source);
        string parent = Path.GetDirectoryName(Path.TrimEndingDirectorySeparator(full))!;
        bool languageDirectory = Directory.Exists(full) && Directory.EnumerateFiles(full, "item*.msgbnd.dcx").Any();
        var directories = languageDirectory
            ? (Path.GetFileName(parent).Equals("msg", StringComparison.OrdinalIgnoreCase) ? Directory.GetDirectories(parent) : new[] { full })
            : (Directory.Exists(full) ? Directory.GetDirectories(full) : Array.Empty<string>());
        var archives = directories.SelectMany(dir => new[] { "item.msgbnd.dcx", "item_dlc01.msgbnd.dcx", "item_dlc02.msgbnd.dcx" }
            .Select(name => Path.Combine(dir, name))).Where(File.Exists).ToArray();
        if (archives.Length == 0) throw new FileNotFoundException($"No item message archives found in {source}.");
        int count = 0;
        foreach (string path in archives)
        {
            var binder = BND4.Read(path);
            string identity = Path.GetFileName(Path.GetDirectoryName(path)) + "/" + Path.GetFileName(path);
            beforeArchive?.Invoke(binder, identity);
            prepare?.Invoke(binder);
            int injected = FmgArchiveService.InjectFmgEntriesIntoBnd(binder, specs);
            transform?.Invoke(binder);
            afterArchive?.Invoke(binder, identity);
            string language = Path.GetFileName(Path.GetDirectoryName(path))!;
            string destination = Path.Combine(Path.GetDirectoryName(regulationOutput)!, "msg", language, Path.GetFileName(path));
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            binder.Write(destination);
            Console.WriteLine($"[RegTool] Injected {injected} item texts into {language}/{Path.GetFileName(path)}.");
            count = Math.Max(count, injected);
        }
        return count;
    }
}
