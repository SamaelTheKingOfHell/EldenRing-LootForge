using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Merge cooldown-limited equipment magic into the existing common event script.</summary>
public sealed class DiabloCombatEvents
{
    public const uint FirstEvent = 1900860000;
    public const uint LastEvent = FirstEvent + 4095;
    readonly Dictionary<int, EMEVD.Event> events = new();
    readonly Dictionary<float, int> projectiles = new();
    public int Count => events.Count;
    static readonly string[] Kinds = { "attack_cast", "guard_cast", "guard_heal", "thorns", "hurt_heal" };
    public static int KindIndex(string kind)
    {
        int index = Array.IndexOf(Kinds, kind);
        return index >= 0 ? index : throw new InvalidDataException($"Unknown Diablo enchantment {kind}.");
    }

    static EMEVD.Instruction Op(int bank, int id, params object[] args) => new(bank, id, args);

    static EMEVD.Instruction Has(sbyte group, int effect, bool have = true) =>
        Op(4, 5, group, 10000u, effect, (byte)(have ? 1 : 0), (sbyte)0, 1f);
    static EMEVD.Instruction Wait(sbyte group) => Op(0, 0, (sbyte)0, (byte)1, group);
    static EMEVD.Instruction Restart() => Op(1000, 4, (byte)1);

    public void Register(string kind, float power, int marker, DiabloEffectService effects,
        Func<string, string?, PARAM> table)
    {
        if (events.ContainsKey(marker)) return;
        KindIndex(kind);
        uint id = FirstEvent + (uint)events.Count;
        if (id > LastEvent) throw new InvalidDataException("Diablo combat event capacity exceeded. Reduce enchanted variants.");
        var ev = new EMEVD.Event(id, EMEVD.Event.RestBehaviorType.Restart);
        events[marker] = ev;
        var ins = ev.Instructions;
        ins.Add(Signature());
        ins.Add(Op(2000, 2, (byte)0)); // Local player only, no network synchronization.
        ins.Add(Has(1, marker));
        ins.Add(Op(4, 14, (sbyte)1, 10000u, (sbyte)2, 0, (sbyte)0, 1f)); // Alive.
        ins.Add(Wait(1));
        if (kind is "thorns" or "hurt_heal")
        {
            // The sentinel is removed by incoming damage. Arm after equipping so
            // merely putting on clothing cannot trigger a heal or retaliation.
            int sentinel = effects.Effect(new() { ["deleteCriteriaDamage"] = 1, ["effectEndurance"] = -1f }, "damage-sentinel:" + id);
            ins.Add(Op(2004, 8, 10000u, sentinel));
            ins.Add(Has(-1, sentinel, false));
            ins.Add(Has(-1, marker, false));
            ins.Add(Wait(-1));
            ins.Add(Op(1004, 2, (byte)1, 10000u, marker, (byte)0, (sbyte)0, 1));
        }
        else
        {
            ins.Add(Has(2, marker));
            ins.Add(Has(2, kind == "attack_cast" ? 146 : 100410));
            ins.Add(Wait(2));
        }
        if (kind is "guard_heal" or "hurt_heal")
        {
            int healing = effects.Effect(new() { ["effectEndurance"] = 0f,
                ["changeHpPoint"] = -(int)Math.Round(20 * power), ["stateInfo"] = 50 });
            ins.Add(Op(2004, 8, 10000u, healing));
        }
        else
        {
            int behavior = Projectile(power, table);
            int shots = kind == "thorns" ? 6 : 1;
            for (int shot = 0; shot < shots; shot++)
                ins.Add(Op(2003, 5, 10000u, 10000u, 220, behavior, 0, shot * 60, 0));
        }
        float cooldown = kind switch { "attack_cast" => 6, "thorns" => 8, "hurt_heal" => 12, _ => 10 };
        ins.Add(Op(1001, 0, cooldown));
        ins.Add(Restart());
    }

    static EMEVD.Instruction Signature() => Op(0, 1, (sbyte)15, (sbyte)0, 0x4c464447, 0x4c464447);

    int Projectile(float power, Func<string, string?, PARAM> table)
    {
        if (projectiles.TryGetValue(power, out int previous)) return previous;
        var bullets = table("Bullet", null);
        var attacks = table("AtkParam_Pc", "AtkParam");
        var behaviors = table("BehaviorParam", "BehaviorParam");
        var pebble = bullets.Rows.FirstOrDefault(row => row.ID == 10400000)
            ?? throw new InvalidDataException("Glintstone projectile template is missing.");
        int attackId = ParamHelper.GetCellInt(pebble, "atkId_Bullet");
        var attack = attacks.Rows.FirstOrDefault(row => row.ID == attackId)
            ?? throw new InvalidDataException($"Glintstone attack template {attackId} is missing.");
        int Free(PARAM p) { var ids = p.Rows.Select(row => row.ID).ToHashSet(); int id = 8600000; while (ids.Contains(id)) id++; return id; }
        var newAttack = new PARAM.Row(attack) { ID = Free(attacks), Name = "[LootForge] Diablo Magic" };
        foreach (string field in new[] { "atkPhys", "atkMag", "atkFire", "atkThun", "atkDark" })
        {
            var cell = ParamHelper.FindCell(newAttack, field);
            if (cell != null) DiabloEffectService.Set(newAttack, field, Math.Clamp(Math.Round((field == "atkMag" ? Math.Max(60, Convert.ToDouble(cell.Value)) : Convert.ToDouble(cell.Value)) * power), 0, 65535));
        }
        // Scripted magic uses its rolled damage, independent of whichever weapon
        // happens to be equipped when the event fires.
        foreach (string field in new[] { "atkPhysCorrection", "atkMagCorrection", "atkFireCorrection", "atkThunCorrection", "atkDarkCorrection" })
            if (ParamHelper.FindCell(newAttack, field) != null) DiabloEffectService.Set(newAttack, field, 0);
        attacks.Rows.Add(newAttack);
        var bullet = new PARAM.Row(pebble) { ID = Free(bullets), Name = "[LootForge] Diablo Projectile" };
        DiabloEffectService.Set(bullet, "atkId_Bullet", newAttack.ID);
        bullets.Rows.Add(bullet);
        var behavior = new PARAM.Row(Free(behaviors), "[LootForge] Diablo Cast", behaviors.AppliedParamdef);
        DiabloEffectService.Set(behavior, "refType", 1);
        DiabloEffectService.Set(behavior, "refId", bullet.ID);
        behaviors.Rows.Add(behavior);
        return projectiles[power] = behavior.ID;
    }

    public void Stage(string outputRegulation, string targetRegulation, string? gameDirectory)
    {
        string relative = Path.Combine("event", "common.emevd.dcx");
        string target = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(targetRegulation))!, relative);
        string source = File.Exists(target) ? target : Path.Combine(gameDirectory ?? "", relative);
        if (!File.Exists(source))
        {
            if (Count == 0) return;
            throw new FileNotFoundException("Combat enchantments need the existing common.emevd.dcx. Supply the unpacked game directory.", source);
        }
        var script = EMEVD.Read(source);
        // Only remove IDs that this feature owns; unrelated mod events survive.
        bool installed = script.Events.Any(ev => ev.ID >= FirstEvent && ev.ID <= LastEvent);
        if (!installed && Count == 0) return;
        if (script.Events.Any(ev => ev.ID >= FirstEvent && ev.ID <= LastEvent &&
            (ev.Instructions.Count == 0 || ev.Instructions[0].Bank != 0 || ev.Instructions[0].ID != 1 ||
             !ev.Instructions[0].ArgData.SequenceEqual(Signature().ArgData))))
            throw new InvalidDataException("Diablo event ID range is occupied by another mod.");
        script.Events.RemoveAll(ev => ev.ID >= FirstEvent && ev.ID <= LastEvent);
        var constructor = script.Events.FirstOrDefault(ev => ev.ID == 0)
            ?? throw new InvalidDataException("Common event constructor is missing.");
        if (constructor.Parameters.Count != 0) throw new InvalidDataException("Parameterized common constructor cannot safely accept Diablo initializers.");
        constructor.Instructions.RemoveAll(ins => ins.Bank == 2000 && ins.ID == 0 &&
            ((ins.ArgData.Length >= 12 && BitConverter.ToUInt32(ins.ArgData, 4) >= FirstEvent && BitConverter.ToUInt32(ins.ArgData, 4) <= LastEvent) ||
             (ins.ArgData.Length == 8 && ins.Layer == 0 && BitConverter.ToUInt32(ins.ArgData, 0) >= FirstEvent && BitConverter.ToUInt32(ins.ArgData, 0) <= LastEvent && BitConverter.ToUInt32(ins.ArgData, 4) == 0)));
        var initializers = new List<EMEVD.Instruction>();
        foreach (var ev in events.Values.OrderBy(ev => ev.ID))
        {
            script.Events.Add(ev);
            initializers.Add(Op(2000, 0, 0, (uint)ev.ID, 0u));
        }
        constructor.Instructions.InsertRange(0, initializers);
        string staged = Path.Combine(Path.GetDirectoryName(outputRegulation)!, relative);
        Directory.CreateDirectory(Path.GetDirectoryName(staged)!);
        script.Write(staged, script.Compression);
    }
}
