using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Materialize Diablo power and passive rolls without changing shared vanilla effects.</summary>
public sealed class DiabloEffectService
{
    readonly Func<string, string, (PARAM Param, BinderFile File)> load;
    readonly Dictionary<string, Dictionary<int, PARAM.Row>> indexes = new();
    readonly Dictionary<string, int> indexedCounts = new();
    readonly Dictionary<string, int> generated = new();
    int nextEffect = 8600000;
    public DiabloCombatEvents Combat { get; } = new();
    public DiabloInfusionState? InfusionState { get; set; }
    public Dictionary<int, int[]> ExpandedItems { get; } = new();
    public HashSet<int> InfusedItemIds { get; } = new();
    readonly DiabloAuraService auras;
    readonly DiabloPassiveService passives;

    public DiabloEffectService(Func<string, string, (PARAM Param, BinderFile File)> load)
    {
        this.load = load;
        foreach (var (table, def) in new[] { ("Bullet", "BulletParam"), ("BehaviorParam", "BehaviorParam") })
            Table(table, def).Rows.RemoveAll(row => row.Name?.StartsWith("[LootForge] Diablo") == true);
        auras = new DiabloAuraService(Table);
        passives = new DiabloPassiveService(()=>Index("SpEffectParam","SpEffect"), Effect);
    }

    PARAM Table(string table, string? def = null) => load(table, def ?? (table == "Bullet" ? "BulletParam" : table)).Param;
    Dictionary<int, PARAM.Row> Index(string table, string? def = null)
    {
        var param = Table(table, def);
        if (!indexes.TryGetValue(table, out var index)) indexes[table] = index = new();
        for (int i = indexedCounts.GetValueOrDefault(table); i < param.Rows.Count; i++)
            index[param.Rows[i].ID] = param.Rows[i];
        indexedCounts[table] = param.Rows.Count;
        return index;
    }

    public int Effect(Dictionary<string, object> fields, string discriminator = "", PARAM.Row? template = null)
    {
        string key = discriminator + JsonSerializer.Serialize(fields.OrderBy(pair => pair.Key));
        if (generated.TryGetValue(key, out int previous)) return previous;
        var param = Table("SpEffectParam", "SpEffect");
        var index = Index("SpEffectParam", "SpEffect");
        while (index.ContainsKey(nextEffect)) nextEffect++;
        var row = template == null ? new PARAM.Row(nextEffect++, "[LootForge] Diablo Effect", param.AppliedParamdef)
            : new PARAM.Row(template) { ID = nextEffect++, Name = "[LootForge] Diablo Scaled Passive" };
        if (template == null)
        {
            Set(row, "effectEndurance", -1f);
            Set(row, "motionInterval", 1f);
            foreach (var name in new[] { "effectTargetSelf", "effectTargetPlayer", "effectTargetLive", "effectTargetGhost" })
                Set(row, name, 1);
        }
        foreach (var (name, value) in fields) Set(row, name, value);
        param.Rows.Add(row);
        index[row.ID] = row;
        generated[key] = row.ID;
        return row.ID;
    }

    public static void Set(PARAM.Row row, string field, object value)
    {
        var cell = ParamHelper.FindCell(row, field) ?? throw new InvalidDataException($"Required Diablo field {field} is missing.");
        ParamHelper.SetCellValue(cell, JsonSerializer.SerializeToElement(value));
    }

    static string[] ResidentSlots(string table) => table switch
    {
        "EquipParamAccessory" => new[] { "refId", "residentSpEffectId1", "residentSpEffectId2", "residentSpEffectId3", "residentSpEffectId4" },
        "EquipParamProtector" => new[] { "residentSpEffectId", "residentSpEffectId2", "residentSpEffectId3" },
        _ => new[] { "residentSpEffectId", "residentSpEffectId1", "residentSpEffectId2" }
    };

    int Attach(PARAM.Row row, string table, int effect, Dictionary<string, object>? additions = null)
    {
        foreach (string name in ResidentSlots(table))
        {
            var cell = ParamHelper.FindCell(row, name);
            if (cell != null && Convert.ToInt32(cell.Value) <= 0)
            {
                Set(row, name, effect);
                return effect;
            }
        }
        // Some crowns use all resident slots. Merge numeric bonuses/markers into
        // an unconditional permanent passive, preserving its original behavior.
        foreach (string name in ResidentSlots(table))
        {
            int originalId = ParamHelper.GetCellInt(row, name);
            if (!Index("SpEffectParam", "SpEffect").TryGetValue(originalId, out var original)) continue;
            if (Convert.ToSingle(ParamHelper.FindCell(original, "effectEndurance")!.Value) >= 0 ||
                Convert.ToSingle(ParamHelper.FindCell(original, "conditionHp")!.Value) >= 0 ||
                Enumerable.Range(1, 3).Any(i => ParamHelper.GetCellInt(original, "invocationConditionsStateChange" + i) != 0)) continue;
            var merged = new Dictionary<string, object>();
            if (additions?.ContainsKey("vfxId") == true &&
                Enumerable.Range(0, 8).All(i => ParamHelper.GetCellInt(original, i == 0 ? "vfxId" : "vfxId" + i) >= 0)) continue;
            foreach (var (key, value) in additions ?? new())
            {
                if (key == "vfxId")
                {
                    string available = Enumerable.Range(0, 8).Select(i => i == 0 ? "vfxId" : "vfxId" + i)
                        .First(field => ParamHelper.GetCellInt(original, field) < 0);
                    merged[available] = value;
                    continue;
                }
                double added = JsonSerializer.SerializeToElement(value).GetDouble();
                double current = Convert.ToDouble(ParamHelper.FindCell(original, key)!.Value);
                merged[key] = key.EndsWith("Rate") ? current * added : current + added;
            }
            int combined = Effect(merged, $"merge:{originalId}:{effect}", original);
            Set(row, name, combined);
            return combined;
        }
        throw new InvalidDataException($"No compatible passive slot on Diablo equipment {row.ID}; refusing a silent lost effect.");
    }

    public void Apply(JsonElement equipment)
    {
        foreach (var ep in equipment.EnumerateArray())
        {
            if (!ep.TryGetProperty("field_updates", out var updates)) continue;
            string table = ep.GetProperty("param_table").GetString()!;
            int itemId = ep.GetProperty("new_param_id").GetInt32();
            if (!Index(table).TryGetValue(itemId, out var row))
                throw new InvalidDataException($"Diablo equipment {itemId} was not injected.");
            var rows = new List<PARAM.Row> { row };
            if (table == "EquipParamWeapon" && ep.TryGetProperty("diablo_infusion_family", out var familyFlag) && familyFlag.GetBoolean())
            {
                families ??= Table(table).Rows.Where(r => r.ID < 90000000).GroupBy(FamilyId)
                    .ToDictionary(group => group.Key, group => group.ToList());
                rows = families.GetValueOrDefault(FamilyId(row), rows);
                ExpandedItems[itemId] = rows.Select(member => member.ID).ToArray();
                foreach (var member in rows)
                    foreach (var field in updates.EnumerateObject())
                        if (!field.Name.StartsWith("_lf_") &&
                            !(updates.TryGetProperty("_lf_diablo_stat_deltas", out var ds) && ds.TryGetProperty(field.Name, out _)) &&
                            ParamHelper.FindCell(member, field.Name) != null)
                            Set(member, field.Name, field.Value);
            }
            foreach (var member in rows)
            {
                ApplyRow(member, table, updates);
                if(table=="EquipParamProtector") DiabloBalanceService.Apply(member,table,
                    updates.TryGetProperty("_lf_diablo_tier",out var tier)?tier.GetInt32():4,0);
            }
        }
    }
    public void Prepare(JsonElement equipment)
    {
        if (InfusionState == null) return;
        foreach (var ep in equipment.EnumerateArray())
        {
            if (!ep.TryGetProperty("update_existing", out var update) || !update.GetBoolean()) continue;
            if (!ep.TryGetProperty("row_name", out var label) || !label.GetString()!.StartsWith("[Vanilla Infused]")) continue;
            string table = ep.GetProperty("param_table").GetString()!;
            if (!Index(table).TryGetValue(ep.GetProperty("new_param_id").GetInt32(), out var row)) continue;
            var rows = new List<PARAM.Row> { row };
            if (table == "EquipParamWeapon" && ep.TryGetProperty("diablo_infusion_family", out var flag) && flag.GetBoolean())
            {
                families ??= Table(table).Rows.Where(r => r.ID < 90000000).GroupBy(FamilyId)
                    .ToDictionary(group => group.Key, group => group.ToList());
                rows = families.GetValueOrDefault(FamilyId(row), rows);
            }
            foreach (var member in rows)
            {
                InfusedItemIds.Add(member.ID);
                InfusionState.Capture(member, table, ep.GetProperty("field_updates"));
            }
        }
    }
    Dictionary<int, List<PARAM.Row>>? families;
    void AttachAura(PARAM.Row row, string table, int visual)
    {
        var index = Index("SpEffectParam", "SpEffect");
        var candidates = ResidentSlots(table).Select(slot => (Slot: slot, Id: ParamHelper.GetCellInt(row, slot)))
            .Where(entry => index.ContainsKey(entry.Id))
            .OrderBy(entry => Convert.ToSingle(ParamHelper.FindCell(index[entry.Id], "effectEndurance")!.Value) >= 0);
        foreach (var entry in candidates)
        {
            var source = index[entry.Id];
            string? available = Enumerable.Range(0, 8).Select(i => i == 0 ? "vfxId" : "vfxId" + i)
                .FirstOrDefault(field => ParamHelper.GetCellInt(source, field) < 0);
            if (available == null) continue;
            int combined = Effect(new() { [available] = visual }, $"aura:{entry.Id}:{visual}", source);
            Set(row, entry.Slot, combined);
            return;
        }
        var fields = new Dictionary<string, object> { ["vfxId"] = visual };
        Attach(row, table, Effect(fields), fields);
    }
    static int FamilyId(PARAM.Row row)
    {
        int origin = ParamHelper.GetCellInt(row, "originEquipWep");
        return origin > 0 ? origin : row.ID - row.ID % 100;
    }
    void ApplyRow(PARAM.Row row, string table, JsonElement updates)
    {
        if (!updates.EnumerateObject().Any(field => field.Name.StartsWith("_lf_diablo_"))) return;
        var effectIds = Index("SpEffectParam", "SpEffect");
        double baseAttack = table == "EquipParamWeapon" ? DiabloBalanceService.TotalAttack(row) : 0;
        var baseDamage = table == "EquipParamWeapon" ? DiabloBalanceService.AttackFields.ToDictionary(field=>field,field=>Convert.ToDouble(ParamHelper.FindCell(row,field)!.Value)) : null;
        foreach (string slot in ResidentSlots(table).Concat(new[] { "spEffectBehaviorId0", "spEffectBehaviorId1", "spEffectBehaviorId2" }))
        {
            var cell = ParamHelper.FindCell(row, slot);
            if (cell != null && Convert.ToInt32(cell.Value) > 0 && !effectIds.ContainsKey(Convert.ToInt32(cell.Value)))
                Set(row, slot, -1);
        }
        if (updates.TryGetProperty("_lf_diablo_stat_deltas", out var deltas))
            foreach (var delta in deltas.EnumerateObject())
            {
                var cell = ParamHelper.FindCell(row, delta.Name);
                if (table == "EquipParamProtector" && DiabloBalanceService.ArmorDelta(row,delta.Name,delta.Value.GetDouble())) continue;
                if (cell != null) Set(row, delta.Name, Convert.ToDouble(cell.Value) + delta.Value.GetDouble());
            }
        if (updates.TryGetProperty("_lf_diablo_passive_scales", out var scales))
        {
            var slots = ResidentSlots(table).Concat(new[] { "spEffectBehaviorId0", "spEffectBehaviorId1", "spEffectBehaviorId2" });
            foreach (string slot in slots)
            {
                var cell = ParamHelper.FindCell(row, slot);
                if (cell != null && scales.TryGetProperty(Convert.ToInt32(cell.Value).ToString(), out var scale))
                    Set(row, slot, ScalePassive(Convert.ToInt32(cell.Value), scale.GetDouble(), new()));
            }
        }
        if (updates.TryGetProperty("_lf_diablo_power", out var power))
        {
            double multiplier = 1 + 0.10 * Math.Clamp(power.GetDouble(), 0, 10);
            var fields = table == "EquipParamWeapon"
                ? new[] { "attackBasePhysics", "attackBaseMagic", "attackBaseFire", "attackBaseThunder", "attackBaseDark" }
                : Array.Empty<string>();
            foreach (string name in fields)
            {
                var cell = ParamHelper.FindCell(row, name);
                if (cell != null) Set(row, name, Math.Clamp(Math.Round(Convert.ToDouble(cell.Value) * multiplier), 0, 65535));
            }
        }
        if (updates.TryGetProperty("_lf_diablo_power", out var inheritedPower))
        {
            foreach (string slot in ResidentSlots(table))
            {
                int effect = ParamHelper.GetCellInt(row,slot);
                if (effect > 0 && effectIds.TryGetValue(effect,out var original) && original.Name?.StartsWith("[LootForge]") != true)
                    Set(row,slot,ScalePassive(effect,inheritedPower.GetDouble(),new()));
            }
            if (updates.TryGetProperty("_lf_diablo_tier",out var region))
                DiabloBalanceService.Apply(row,table,region.GetInt32(),inheritedPower.GetDouble(),baseAttack,baseDamage);
        }
        if (updates.TryGetProperty("_lf_diablo_on_hit",out var onHit))
            foreach(var hit in onHit.EnumerateArray())
            {
                double strength=hit.GetProperty("power").GetDouble();
                if(strength<=0)continue;
                string? slot=Enumerable.Range(0,3).Select(i=>"spEffectBehaviorId"+i).FirstOrDefault(name=>ParamHelper.GetCellInt(row,name)<=0);
                if(slot==null)continue;
                Set(row,slot,ScalePassive(hit.GetProperty("id").GetInt32(),strength,new()));
                int message=hit.TryGetProperty("msg_id",out var msg)?msg.GetInt32():0;
                AddMessage(row,message);
            }
        if(updates.TryGetProperty("_lf_diablo_messages",out var messages))
            foreach(var message in messages.EnumerateArray())AddMessage(row,message.GetInt32());
        if (updates.TryGetProperty("_lf_diablo_passives", out var passives))
        {
            var fields = passives.EnumerateObject().ToDictionary(p => p.Name, p => (object)p.Value.Clone());
            Attach(row, table, Effect(fields), fields);
        }
        if (updates.TryGetProperty("_lf_diablo_aura", out var aura))
            AttachAura(row, table, auras.Visual(aura.GetString()!, table == "EquipParamWeapon"));
        if (updates.TryGetProperty("_lf_diablo_proc", out var proc))
        {
            string kind = proc.GetProperty("kind").GetString()!;
            float strength = (float)Math.Clamp(Math.Round(proc.GetProperty("power").GetDouble() * 4) / 4, 0.25, 4);
            int marker = Effect(new() { ["effectEndurance"] = -1f }, $"proc:{kind}:{strength}");
            marker = Attach(row, table, marker);
            Combat.Register(kind, strength, marker, this, Table);
        }
    }
    static void AddMessage(PARAM.Row row,int message)
    {
        if(message<=0||Enumerable.Range(0,3).Any(i=>ParamHelper.GetCellInt(row,"spEffectMsgId"+i)==message))return;
        string? slot=Enumerable.Range(0,3).Select(i=>"spEffectMsgId"+i).FirstOrDefault(name=>ParamHelper.GetCellInt(row,name)<=0);
        if(slot!=null)Set(row,slot,message);
    }
    int ScalePassive(int source,double power,HashSet<int> path) => passives.Scale(source,power,path);
}
