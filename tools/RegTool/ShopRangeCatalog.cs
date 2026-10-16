using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Shop intervals opened by the installed talk scripts, rather than invented row ranges.</summary>
public static class ShopRangeCatalog
{
    public record Shop(int Start, int End, string Name, EntityProgressionTier Tier, string Evidence, int FreeRows = 0, bool IsExchange = false);
    public static int? Constant(byte[] expression)
    {
        if (expression.Length == 2 && expression[1] == 0xa1 && expression[0] <= 0x7f) return expression[0] - 64;
        if (expression.Length == 6 && expression[0] == 0x82 && expression[5] == 0xa1) return BitConverter.ToInt32(expression, 1);
        return null;
    }
    public static List<Shop> Load(string profile, string? game, string defs, PARAM? table = null)
    {
        var result = new Dictionary<(int, int), Shop>();
        var names = WorldLootCatalog.Names(defs, "ShopLineupParam");
        foreach (string path in WorldLootCatalog.Files(profile, game, "script/talk", "*.talkesdbnd.dcx"))
        {
            var binder = BND4.Read(path);
            foreach (var file in binder.Files)
            {
                var esd = ESD.Read(file.Bytes);
                foreach (var states in esd.StateGroups.Values)
                    foreach (var state in states.Values)
                        foreach (var command in state.EntryCommands.Concat(state.WhileCommands).Concat(state.ExitCommands))
                        {
                            if (command.CommandBank != 1 || command.CommandID is not (22 or 111) || command.Arguments.Count != 2) continue;
                            int? start = Constant(command.Arguments[0]), end = Constant(command.Arguments[1]);
                            if (start is null || end is null || start < 0 || end < start || end - start > 5000) continue;
                            bool exchange = command.CommandID == 111;
                            string name = exchange ? "Finger Reader Enia" : names.GetValueOrDefault(start.Value, "Merchant " + start);
                            if (name.StartsWith('[') && name.Contains(']')) name = name[1..name.IndexOf(']')];
                            int free = table == null ? 0 : Enumerable.Range(start.Value, end.Value-start.Value+1)
                                .Count(id=>!table.Rows.Any(row=>row.ID==id && row.Name?.Contains("[LootForge]") != true));
                            var candidate = new Shop(start.Value,end.Value,name,WorldLootCatalog.Tier(Path.GetFileName(path), name),
                                Path.GetFileName(path) + ":" + Path.GetFileName(file.Name),free,exchange);
                            if (!result.TryGetValue((start.Value,end.Value),out var prior) || candidate.Tier < prior.Tier)
                                result[(start.Value,end.Value)] = candidate;
                        }
            }
        }
        return result.Values.OrderBy(shop => shop.Start).ToList();
    }
}
