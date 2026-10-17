using System.Text.Json;
using LootForge.RegTool;
using SoulsFormats;

string root = args.Length > 0 ? args[0] : Directory.GetCurrentDirectory();
if (args.Length == 5 && args[1] == "audit")
{
    ProfileAudit.Run(root, args[2], args[3], args[4]);
    return;
}
string defs = Path.Combine(root, "tools/vendor/Paramdex/ER/Defs");
int checks = 0;
void Check(bool condition, string name)
{
    if (!condition) throw new Exception("FAILED: " + name);
    checks++;
    Console.WriteLine("PASS: " + name);
}
PARAM Table(string defName)
{
    var def = PARAMDEF.XmlDeserialize(Path.Combine(defs, defName + ".xml"), false, false);
    var param = new PARAM { Rows = new(), ParamType = def.ParamType };
    param.ApplyParamdef(def);
    return param;
}
PARAM.Row Row(PARAM param, int id, string name = "Fixture")
{
    var row = new PARAM.Row(id, name, param.AppliedParamdef);
    param.Rows.Add(row);
    return row;
}

var lots = Table("ItemLotParam");
var lot = Row(lots, 10030, "Limgrave chest");
ParamHelper.SetCellIfExists(lot, "lotItemId01", 700);
ParamHelper.SetCellIfExists(lot, "lotItemId02", 800);
var layout = ItemLotLayout.Extract(lots);
Check(ParamHelper.GetCellInt(lot, "LOTITEMID01") == 700, "case-insensitive indexed fields");
Check(ParamHelper.FindCell(lot, "absent") == null, "missing fields remain optional");
Check(ReferenceEquals(layout, ItemLotLayout.Extract(lots)), "loot layouts are reused");

var dupTable = Table("ItemLotParam");
var r1 = Row(dupTable, 16000500, "First Instance");
var r2 = Row(dupTable, 16000500, "Duplicate Instance");
var dupDict = dupTable.ToRowDictionary();
Check(dupDict.Count == 1 && dupDict[16000500].Name == "First Instance", "ToRowDictionary retains first entry dynamically on duplicate row IDs");

AdditiveLootChecks.Run(defs, Check);
DropBudgetChecks.Run(defs, Check);
BalanceChecks.Run(defs, Check);

var chain = Row(lots, 10031, "Existing vanilla reward");
ParamHelper.SetCellIfExists(chain, "lotItemId01", 12345);
ParamHelper.SetCellIfExists(chain, "lotItemCategory01", 4);
var enemy = Table("ItemLotParam");
var tutorial = Row(enemy, 431100000, "Soldier of Godrick");
ParamHelper.SetCellIfExists(tutorial, "lotItemId01", 54321);
BossLootPoolService.EnrichBossLootPools(enemy, lots, null, null, 2);
Check(ParamHelper.GetCellInt(chain, "lotItemId01") == 12345, "boss enrichment preserves existing chained reward");
Check(ParamHelper.GetCellInt(tutorial, "lotItemId01") == 54321, "tutorial enrichment preserves original reward");
ChestLootPoolService.EnrichChestLootPools(lots, enemy, Table("EquipParamProtector"), Table("EquipParamWeapon"), 1, 2);
Check(ParamHelper.GetCellInt(chain, "lotItemId01") == 12345, "chest enrichment preserves existing chained reward");

var weapon = Table("EquipParamWeapon");
var blade = Row(weapon, 2020000);
foreach (var field in new[] { "wepType", "isDeposit", "sortId", "equipModelId", "gemMountType" })
    ParamHelper.SetCellIfExists(blade, field, 1);
ParamHelper.SetCellIfExists(blade, "attackBasePhysics", (ushort)100);
ParamHelper.SetCellIfExists(blade, "swordArtsParamId", 555);
ParamHelper.SetCellIfExists(blade, "correctStrength", 10.5f);
ParamHelper.SetCellIfExists(blade, "iconId", (ushort)2020);
blade.Name = null!;
Check(WeaponInjector.IsValidWeaponRow(blade), "nameless retail weapons remain valid clone sources");
var armor = Table("EquipParamProtector");
var armorRow = Row(armor, 40100);
armorRow.Name = null!;
ParamHelper.SetCellIfExists(armorRow, "iconIdM", (ushort)13001);
Check(ProtectorInjector.IsValidProtectorRow(armorRow), "nameless retail armor remains a valid clone source");
var generated = new PARAM.Row(blade) { ID = 100000000, Name = "[LootForge] Custom" };
weapon.Rows.Add(generated);
var tables = new Dictionary<string, PARAM> { ["EquipParamWeapon"] = weapon,
    ["EquipParamProtector"] = Table("EquipParamProtector"), ["EquipParamAccessory"] = Table("EquipParamAccessory") };
(PARAM, BinderFile) Load(string table, string def) => (tables[table], new BinderFile());
var effects = UniversalSweeperService.InfuseParams(Load, false, 42);
int attack = ParamHelper.GetCellInt(blade, "attackBasePhysics");
Check(attack > 100, "vanilla infusion changes eligible stats");
float strength = Convert.ToSingle(ParamHelper.FindCell(blade, "correctStrength")!.Value);
Check(strength % 1 == 0.5f, "infusion preserves fractional weapon scaling");
Check(ParamHelper.GetCellInt(generated, "attackBasePhysics") == 100, "generated relics are not infused twice");
Check(ParamHelper.GetCellInt(blade, "swordArtsParamId") == 555, "disabled skill randomization is respected");
UniversalSweeperService.InfuseParams(Load, false, 42);
Check(ParamHelper.GetCellInt(blade, "attackBasePhysics") == attack, "repeated infusion does not compound stats");

var archive = new BND4();
foreach (string filename in new[] { "WeaponName.fmg", "WeaponName_dlc01.fmg", "WeaponName_dlc02.fmg" })
{
    var fmg = new FMG();
    fmg.Entries.Add(new FMG.Entry(2020000, "Sword"));
    fmg.Entries.Add(new FMG.Entry(987654, "DLC-exclusive retained"));
    archive.Files.Add(new BinderFile(Binder.FileFlags.Flag1, filename, fmg.Write()));
}
SweepFmgService.Apply(archive, effects);
Check(archive.Files.All(f => FMG.Read(f.Bytes).Entries.First(e => e.ID == 2020000).Text == "Sword"), "legacy infusion preserves vanilla names in all DLC variants");
Check(archive.Files.All(f => FMG.Read(f.Bytes).Entries.Any(e => e.ID == 987654 && e.Text == "DLC-exclusive retained")), "DLC-exclusive text is retained");

using var invalid = JsonDocument.Parse("[{\"equip_params\":[{\"param_table\":\"EquipParamWeapon\",\"new_param_id\":2020000}]}]");
bool rejected = false;
try { PatchPreflight.Validate(invalid.RootElement.EnumerateArray(), Load); }
catch (InvalidDataException) { rejected = true; }
Check(rejected, "preflight rejects collisions with existing game items");

string temporary = Path.Combine(Path.GetTempPath(), "lootforge-check-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(temporary);
try
{
    // Actual extraction roundtrip: attack and bullet IDs may coincide but refer
    // to different tables. Only refType 0 is an AtkParam_Pc dependency.
    var importWeapon = Table("EquipParamWeapon");
    var selected = Row(importWeapon, 100000000, "Selected custom weapon");
    ParamHelper.SetCellIfExists(selected, "equipModelId", (ushort)556);
    ParamHelper.SetCellIfExists(selected, "behaviorVariationId", 900);
    var importBehavior = Table("BehaviorParam");
    foreach (var (id, type, reference) in new[] { (100900001, 0, 77), (100900002, 1, 11), (100900003, 2, 88) })
    {
        var row = Row(importBehavior, id);
        ParamHelper.SetCellIfExists(row, "variationId", 900);
        ParamHelper.SetCellIfExists(row, "refType", (byte)type);
        ParamHelper.SetCellIfExists(row, "refId", reference);
    }
    var importAttack = Table("AtkParam");
    Row(importAttack, 77);
    Row(importAttack, 11);
    Row(importAttack, 88);
    var importSkill = Table("SwordArtsParam");
    Row(importSkill, 1);
    var fixture = new BND4();
    foreach (var (name, param) in new[] { ("EquipParamWeapon", importWeapon), ("BehaviorParam_PC", importBehavior),
                 ("AtkParam_Pc", importAttack), ("SwordArtsParam", importSkill) })
    {
        param.ParamdefDataVersion = param.AppliedParamdef.DataVersion;
        fixture.Files.Add(new BinderFile(Binder.FileFlags.Flag1, name + ".param", param.Write()));
    }
    string fixturePath = Path.Combine(temporary, "extract-fixture.bin");
    SoulsFormats.Cryptography.RegulationDecryptor.EncryptERRegulation(fixturePath, fixture);
    string extractionPath = Path.Combine(temporary, "extract-fixture.json");
    int extractionCode = SkillMovesetService.ExecuteExtractSkillsMovesets(new()
        { ["input"] = fixturePath, ["defs"] = defs, ["output"] = extractionPath });
    using var extracted = JsonDocument.Parse(File.ReadAllText(extractionPath));
    var extractedAttacks = extracted.RootElement.GetProperty("CustomAttacks");
    Check(extractionCode == 0 && extractedAttacks.TryGetProperty("77", out _), "native extraction includes actual attack dependencies");
    Check(!extractedAttacks.TryGetProperty("11", out _) && !extractedAttacks.TryGetProperty("88", out _), "native extraction does not confuse bullets/effects with attacks");
    Check(extracted.RootElement.GetProperty("SchemaVersion").GetInt32() == 2, "corrected extraction is explicitly versioned");

    string target = Path.Combine(temporary, "regulation.bin");
    File.WriteAllText(target, "original");
    using (var transaction = new PatchOutputTransaction(target))
        File.WriteAllText(transaction.RegulationPath, "uncommitted");
    Check(File.ReadAllText(target) == "original", "failed/uncommitted patch leaves original output intact");
    File.WriteAllText(Path.Combine(temporary, "msg"), "blocks message directory");
    bool commitFailed = false;
    using (var transaction = new PatchOutputTransaction(target))
    {
        File.WriteAllText(transaction.RegulationPath, "must roll back");
        string stagedMessage = Path.Combine(Path.GetDirectoryName(transaction.RegulationPath)!, "msg", "engUS", "item.msgbnd.dcx");
        Directory.CreateDirectory(Path.GetDirectoryName(stagedMessage)!);
        File.WriteAllText(stagedMessage, "message");
        try { transaction.Commit(); }
        catch (IOException) { commitFailed = true; }
    }
    Check(commitFailed && File.ReadAllText(target) == "original", "commit failure rolls back previously replaced regulation");
    File.Delete(Path.Combine(temporary, "msg"));
    using (var transaction = new PatchOutputTransaction(target))
    {
        File.WriteAllText(transaction.RegulationPath, "completed");
        transaction.Commit();
    }
    Check(File.ReadAllText(target) == "completed", "completed patch replaces output");
    Check(!Directory.EnumerateDirectories(temporary).Any(), "transaction staging is cleaned");
}
finally { Directory.Delete(temporary, true); }
Console.WriteLine($"{checks} native checks passed.");
