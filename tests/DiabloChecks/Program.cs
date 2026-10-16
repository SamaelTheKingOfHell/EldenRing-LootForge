using System.Text.Json;
using System.Runtime.InteropServices;
using SoulsFormats;
using SoulsFormats.Cryptography;
using LootForge.RegTool;

string root = args[0], source = args[1], specsPath = args[2], game = args[3], output = args[4];
Directory.CreateDirectory(output);
SoulsFormats.Oodle.Oodle6Ptr = System.Runtime.InteropServices.NativeLibrary.Load(Path.Combine(game, "oo2core_6_win64.dll"));
if (args.Length > 7 && args[5] == "compare-events")
{
    var firstBytes = DCX.Decompress(File.ReadAllBytes(args[6]));
    var secondBytes = DCX.Decompress(File.ReadAllBytes(args[7]));
    string Snapshot(string path) => JsonSerializer.Serialize(EMEVD.Read(path));
    string firstSnapshot = Snapshot(args[6]), secondSnapshot = Snapshot(args[7]);
    File.WriteAllText(Path.Combine(output, "initial-events.json"), firstSnapshot);
    File.WriteAllText(Path.Combine(output, "reforge-events.json"), secondSnapshot);
    bool logicalEqual = firstSnapshot == secondSnapshot;
    Console.WriteLine(JsonSerializer.Serialize(new { uncompressedEqual = firstBytes.SequenceEqual(secondBytes), logicalEqual }));
    if (!logicalEqual) throw new Exception("Reforge changed common event contents.");
    return;
}
var bnd = RegulationDecryptor.DecryptERRegulation(source);
var cache = new Dictionary<string, (PARAM Param, BinderFile File)>();
(PARAM Param, BinderFile File) Load(string name, string defName)
{
    if (cache.TryGetValue(name, out var prior)) return prior;
    var file = bnd.Files.Single(file => file.Name.EndsWith("/" + name + ".param", StringComparison.OrdinalIgnoreCase) ||
        file.Name.EndsWith("\\" + name + ".param", StringComparison.OrdinalIgnoreCase) || file.Name == name + ".param");
    var param = PARAM.Read(file.Bytes);
    var def = PARAMDEF.XmlDeserialize(Path.Combine(root, "tools/vendor/Paramdex/ER/Defs", defName + ".xml"), false, false);
    if (defName == "SpEffect") ParamdefBitPadding.Preserve(def);
    param.ApplyParamdefSomewhatCarefully(def);
    return cache[name] = (param, file);
}
if (args.Length > 5 && args[5] == "verify-disabled")
{
    int checkedFields = 0;
    string parent = Path.GetDirectoryName(Path.GetFullPath(source))!;
    using var state = JsonDocument.Parse(File.ReadAllText(Path.Combine(parent, DiabloInfusionState.Filename)));
    foreach (var table in state.RootElement.EnumerateObject())
    {
        var rows = Load(table.Name, table.Name).Param.Rows.ToDictionary(row => row.ID);
        foreach (var row in table.Value.EnumerateObject())
            foreach (var field in row.Value.EnumerateObject())
            {
                string original = field.Value.GetProperty("Original").ToString();
                if (JsonSerializer.SerializeToElement(ParamHelper.FindCell(rows[int.Parse(row.Name)], field.Name)!.Value).ToString() != original)
                    throw new Exception("Disabled field not restored: " + row.Name + "/" + field.Name);
                checkedFields++;
            }
    }
    foreach (var (table, def) in new[] { ("SpEffectParam", "SpEffect"), ("SpEffectVfxParam", "SpEffectVfx"), ("Bullet", "BulletParam"), ("BehaviorParam", "BehaviorParam"), ("AtkParam_Pc", "AtkParam") })
        if (Load(table, def).Param.Rows.Any(row => row.Name?.StartsWith("[LootForge] Diablo") == true))
            throw new Exception("Disabled output retains generated Diablo rows in " + table);
    if (EMEVD.Read(Path.Combine(parent, "event/common.emevd.dcx")).Events.Any(ev => ev.ID >= DiabloCombatEvents.FirstEvent && ev.ID <= DiabloCombatEvents.LastEvent))
        throw new Exception("Disabled output retains combat events.");
    int checkedTexts = 0;
    using var texts = JsonDocument.Parse(File.ReadAllText(Path.Combine(parent, DiabloTextState.Filename)));
    foreach (var archive in texts.RootElement.EnumerateObject())
    {
        var binder = BND4.Read(Path.Combine(parent, "msg", archive.Name));
        var files = binder.Files.ToDictionary(file => Path.GetFileName(file.Name));
        foreach (var file in archive.Value.EnumerateObject())
        {
            var entries = FMG.Read(files[file.Name].Bytes).Entries.ToDictionary(entry => entry.ID);
            foreach (var text in file.Value.EnumerateObject())
            {
                entries.TryGetValue(int.Parse(text.Name), out var entry);
                bool exists = text.Value.GetProperty("OriginalExists").GetBoolean();
                string? original = text.Value.GetProperty("Original").GetString();
                if ((entry != null) != exists || entry?.Text != original)
                    throw new Exception("Disabled text not restored: " + archive.Name + "/" + file.Name + "/" + text.Name);
                checkedTexts++;
            }
        }
    }
    Console.WriteLine($"PASS {checkedFields} restored fields; {checkedTexts} restored texts; no generated Diablo effects, visuals, bullets, behaviors, attacks or events remain.");
    return;
}
if (args.Length > 5 && args[5] == "inspect-auras")
{
    var auraEffects = Load("SpEffectParam", "SpEffect").Param;
    var vfx = Load("SpEffectVfxParam", "SpEffectVfx").Param.Rows.ToDictionary(row => row.ID);
    var catalog = new List<object>();
    foreach (int id in new[] { 3310,6400,6500,6702,1643000,1643100,1647000,1648000,1626000,1632000 })
    {
        var effect = auraEffects.Rows.FirstOrDefault(row => row.ID == id);
        if (effect == null) continue;
        var refs = effect.Cells.Where(cell => cell.Def.InternalName.StartsWith("vfxId") && Convert.ToInt32(cell.Value) >= 0)
            .Select(cell => Convert.ToInt32(cell.Value)).Distinct().ToArray();
        catalog.Add(new { id, state = ParamHelper.GetCellInt(effect,"stateInfo"), cycle = ParamHelper.GetCellInt(effect,"cycleOccurrenceSpEffectId"),
            visuals = refs.Select(reference => new { id=reference, fields=vfx.TryGetValue(reference,out var row) ? row.Cells.Where(cell => cell.Def.InternalName.Contains("Sfx") || cell.Def.InternalName.Contains("Dmy") || cell.Def.InternalName.Contains("Category") || cell.Def.InternalName.Contains("Priority") || cell.Def.InternalName=="effectType").ToDictionary(cell=>cell.Def.InternalName,cell=>cell.Value) : null }) });
    }
    File.WriteAllText(Path.Combine(output,"aura-catalog.json"),JsonSerializer.Serialize(catalog,new JsonSerializerOptions { WriteIndented=true }));
    Console.WriteLine("Aura templates inspected");
    return;
}
var messages = new List<string>();
void Check(bool condition, string text)
{
    if (!condition) throw new Exception(text);
    messages.Add("PASS " + text);
}
using var specs = JsonDocument.Parse(File.ReadAllText(specsPath));
// A selected profile may already contain a previous infusion. Restore its tracked
// native fields in memory before cloning coverage fixtures, as production forging does.
_ = new DiabloInfusionState(source, Load);
var service = new DiabloEffectService(Load);
int equipmentCount = 0;
var inspected = new List<object>();
foreach (var spec in specs.RootElement.EnumerateArray())
{
    var eps = spec.GetProperty("equip_params");
    foreach (var ep in eps.EnumerateArray())
    {
        string table = ep.GetProperty("param_table").GetString()!;
        var param = Load(table, table).Param;
        int id = ep.GetProperty("new_param_id").GetInt32();
        int baseId = ep.GetProperty("base_clone_id").GetInt32();
        var original = param.Rows.First(row => row.ID == baseId);
        var row = new PARAM.Row(original) { ID = id, Name = "[LootForge] Diablo Check" };
        foreach (var property in ep.GetProperty("field_updates").EnumerateObject())
        {
            if (property.Name.StartsWith("_lf_")) continue;
            if (ep.GetProperty("field_updates").TryGetProperty("_lf_diablo_stat_deltas", out var ds) && ds.TryGetProperty(property.Name, out _)) continue;
            var cell = ParamHelper.FindCell(row, property.Name);
            if (cell != null) ParamHelper.SetCellValue(cell, property.Value);
        }
        param.Rows.Add(row);
        equipmentCount++;
    }
    service.Apply(eps);
}
Check(equipmentCount > 100, "real installed equipment templates accepted generated rolls");
Check(service.Combat.Count >= 5, "all five combat enchantments generated native events");
var weaponsForState = Load("EquipParamWeapon", "EquipParamWeapon").Param;
var stateBlade = weaponsForState.Rows.First(row => row.ID == 2020000);
int originalPower = ParamHelper.GetCellInt(stateBlade, "attackBasePhysics");
string stateDirectory = Path.Combine(output, "state-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(stateDirectory);
string stateTarget = Path.Combine(stateDirectory, "regulation.bin");
var infusion = new DiabloInfusionState(stateTarget, Load);
infusion.Capture(stateBlade, "EquipParamWeapon", JsonSerializer.SerializeToElement(new { attackBasePhysics = 1 }));
DiabloEffectService.Set(stateBlade, "attackBasePhysics", originalPower + 7);
infusion.Stage(stateTarget);
_ = new DiabloInfusionState(stateTarget, Load);
Check(ParamHelper.GetCellInt(stateBlade, "attackBasePhysics") == originalPower, "disabling/rerolling restores the pre-infusion base");
DiabloEffectService.Set(stateBlade, "attackBasePhysics", originalPower + 13);
_ = new DiabloInfusionState(stateTarget, Load);
Check(ParamHelper.GetCellInt(stateBlade, "attackBasePhysics") == originalPower + 13, "intervening external stat edits survive restoration");
DiabloEffectService.Set(stateBlade, "attackBasePhysics", originalPower);
var upgrade = new PARAM.Row(stateBlade) { ID = 2020099, Name = "Controlled family member" };
DiabloEffectService.Set(upgrade, "originEquipWep", 2020000);
DiabloEffectService.Set(upgrade, "attackBasePhysics", originalPower + 30);
weaponsForState.Rows.Add(upgrade);
int upgradePower = ParamHelper.GetCellInt(upgrade, "attackBasePhysics");
using var familySpec = JsonDocument.Parse("[{\"param_table\":\"EquipParamWeapon\",\"new_param_id\":2020000,\"diablo_infusion_family\":true,\"field_updates\":{\"_lf_diablo_power\":1}}]");
service.Apply(familySpec.RootElement);
Check(ParamHelper.GetCellInt(upgrade, "attackBasePhysics") == (int)Math.Round(upgradePower * 1.1), "controlled family member gets the same regional bonus on its own base damage");
var textFixture = new FMG();
textFixture.Entries.Add(new FMG.Entry(2020000, "Original blade"));
var archiveFixture = new BND4();
archiveFixture.Files.Add(new BinderFile(Binder.FileFlags.Flag1, 1, "WeaponName.fmg", textFixture.Write()));
var textSpecs = new List<FmgInjector.FmgTextSpec> {
    new(2020000, 2020000, true, "[Rare] Original blade", "Rolled caption", "Info"),
    new(2020001, 2020000, true, "[Rare] Extra blade", "Rolled caption", "Info")
};
var textState = new DiabloTextState(stateTarget, textSpecs);
textState.Prepare(archiveFixture, "engUS/item.msgbnd.dcx");
FmgInjector.InjectFmgEntriesIntoBnd(archiveFixture, textSpecs);
textState.Observe(archiveFixture, "engUS/item.msgbnd.dcx");
textState.Stage(stateTarget);
var disabledText = new DiabloTextState(stateTarget, new());
disabledText.Prepare(archiveFixture, "engUS/item.msgbnd.dcx");
var restoredNames = FMG.Read(archiveFixture.Files[0].Bytes);
Check(restoredNames.Entries.Single(entry => entry.ID == 2020000).Text == "Original blade", "disabling infusion restores original item names");
Check(!restoredNames.Entries.Any(entry => entry.ID == 2020001), "disabling infusion removes text that did not exist originally");
restoredNames.Entries.Single(entry => entry.ID == 2020000).Text = "External rename";
archiveFixture.Files[0].Bytes = restoredNames.Write();
new DiabloTextState(stateTarget, new()).Prepare(archiveFixture, "engUS/item.msgbnd.dcx");
Check(FMG.Read(archiveFixture.Files[0].Bytes).Entries.Single(entry => entry.ID == 2020000).Text == "External rename", "external item renames survive text restoration");
var auraRows = Load("SpEffectVfxParam", "SpEffectVfx").Param.Rows
    .Where(row => row.Name?.StartsWith("[LootForge] Diablo Aura") == true).ToArray();
foreach (var visual in auraRows)
{
    Check(ParamHelper.GetCellInt(visual, "playPriority") == 255, "temporary buffs outrank cosmetic aura " + visual.ID);
    Check(ParamHelper.GetCellInt(visual, "initSfxId") == -1 && ParamHelper.GetCellInt(visual, "finishSfxId") == -1,
        "persistent aura has no equip/unequip burst " + visual.ID);
}
foreach (var effect in Load("SpEffectParam", "SpEffect").Param.Rows.Where(row => row.Name == "[LootForge] Diablo Effect" && ParamHelper.GetCellInt(row, "vfxId") >= 8600000))
{
    Check(ParamHelper.GetCellInt(effect, "stateInfo") == 0 && ParamHelper.GetCellInt(effect, "spCategory") == 0,
        "cosmetic aura does not inherit weapon-buff state or category " + effect.ID);
}
var effects = Load("SpEffectParam", "SpEffect").Param.Rows.Select(row => row.ID).ToHashSet();
foreach (var (name, pair) in cache.ToArray())
{
    Check(pair.Param.Rows.Select(row => row.ID).Distinct().Count() == pair.Param.Rows.Count, name + " has no duplicate IDs");
    byte[] bytes = ParamSerialization.Write(pair.Param);
    var read = PARAM.Read(bytes);
    Check(read.Rows.Count == pair.Param.Rows.Count, name + " binary row count round-trips");
    if (name == "SpEffectParam")
    {
        read.ApplyParamdef(pair.Param.AppliedParamdef);
        var retained = read.Rows.ToDictionary(row => row.ID);
        foreach (var row in pair.Param.Rows)
            foreach (var cell in row.Cells.Where(cell => cell.Def.InternalName.StartsWith("_lf_preserved_bits_") && Convert.ToInt32(cell.Value) != 0))
                Check(ParamHelper.GetCellInt(retained[row.ID], cell.Def.InternalName) == Convert.ToInt32(cell.Value), "undocumented effect bits retained on " + row.ID);
    }
    pair.File.Bytes = bytes;
    if (name.StartsWith("EquipParam"))
        foreach (var row in pair.Param.Rows.Where(row => row.ID >= 180000000))
            foreach (var cell in row.Cells.Where(cell => cell.Def.InternalName.StartsWith("residentSpEffectId") ||
                         cell.Def.InternalName.StartsWith("spEffectBehaviorId")))
                Check(Convert.ToInt32(cell.Value) <= 0 || effects.Contains(Convert.ToInt32(cell.Value)), "effect reference on " + row.ID + "/" + cell.Def.InternalName);
}
string outReg = Path.Combine(output, "regulation.bin");
service.Combat.Stage(outReg, outReg, game);
string eventFile = Path.Combine(output, "event/common.emevd.dcx");
var script = EMEVD.Read(eventFile);
int InitializerCount(EMEVD value) => value.Events.First(ev => ev.ID == 0).Instructions.Count(ins =>
    ins.Bank == 2000 && ins.ID == 0 && ins.ArgData.Length == 12 &&
    BitConverter.ToUInt32(ins.ArgData, 4) >= DiabloCombatEvents.FirstEvent && BitConverter.ToUInt32(ins.ArgData, 4) <= DiabloCombatEvents.LastEvent);
Check(InitializerCount(script) == service.Combat.Count, "combat initializers contain slot, event ID and argument payload");
var lengths = new Dictionary<(int, int), int> { [(0,1)]=12, [(2000,2)]=4, [(4,5)]=20, [(4,14)]=24,
    [(0,0)]=4, [(2004,8)]=8, [(1004,2)]=20, [(2003,5)]=28, [(1001,0)]=4, [(1000,4)]=4 };
foreach (var ev in script.Events.Where(ev => ev.ID >= DiabloCombatEvents.FirstEvent && ev.ID <= DiabloCombatEvents.LastEvent))
    foreach (var ins in ev.Instructions)
        Check(ins.Layer == null && ins.ArgData.Length == lengths[(ins.Bank,ins.ID)], "combat instruction argument layout " + ev.ID + "/" + ins.Bank + "/" + ins.ID);
Check(script.Events.First(ev => ev.ID == 0).Instructions[0].Bank == 2000,
    "combat initializers precede existing constructor control flow");
var originalScript = EMEVD.Read(Path.Combine(game, "event/common.emevd.dcx"));
var originalIds = originalScript.Events.Select(ev => ev.ID).ToHashSet();
Check(originalIds.IsSubsetOf(script.Events.Select(ev => ev.ID)), "all original common events retained");
Check(script.Events.Count == originalScript.Events.Count + service.Combat.Count, "common script event count round-trips");
service.Combat.Stage(outReg, outReg, game);
Check(EMEVD.Read(eventFile).Events.Count == script.Events.Count && InitializerCount(EMEVD.Read(eventFile)) == service.Combat.Count, "reforge does not duplicate event initializers");
new DiabloCombatEvents().Stage(outReg, outReg, game);
Check(EMEVD.Read(eventFile).Events.Count == originalScript.Events.Count, "disabled enchantments remove only generated events");
service.Combat.Stage(outReg, outReg, game);
RegulationDecryptor.EncryptERRegulation(outReg, bnd);
File.WriteAllText(Path.Combine(output, "checks.json"), JsonSerializer.Serialize(new {
    source, equipmentCount, combatEvents = service.Combat.Count, auraVisuals = auraRows.Length, checks = messages.Count,
    coverage = "Installed game PARAM templates and binary serialization; no in-game combat execution",
    results = messages
}, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"PASS {messages.Count} checks; {equipmentCount} items; {service.Combat.Count} combat events. Report: {output}");
