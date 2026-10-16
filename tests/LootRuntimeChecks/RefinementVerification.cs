using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;
using LootForge.RegTool;

/// <summary>Prove new balance/economy and restoration of every tracked vanilla text in the actual output.</summary>
public static class RefinementVerification
{
 public static void MigrateMessages(string root,string baseline,string target,string game)
 {
  SoulsFormats.Oodle.Oodle6Ptr=System.Runtime.InteropServices.NativeLibrary.Load(Path.Combine(game,"oo2core_6_win64.dll"));
  PARAM Load(string path){var bnd=RegulationDecryptor.DecryptERRegulation(path);var p=PARAM.Read(bnd.Files.Single(f=>f.Name.EndsWith("EquipParamWeapon.param",StringComparison.OrdinalIgnoreCase)).Bytes);
   p.ApplyParamdefSomewhatCarefully(PARAMDEF.XmlDeserialize(Path.Combine(root,"tools/vendor/Paramdex/ER/Defs/EquipParamWeapon.xml"),false,false));return p;}
  var before=Load(Path.Combine(baseline,"regulation.bin")).Rows.ToDictionary(r=>r.ID);var current=Load(target).Rows.ToDictionary(r=>r.ID);
  var options=new JsonSerializerOptions();string statePath=Path.Combine(Path.GetDirectoryName(target)!,DiabloInfusionState.Filename);
  var states=JsonSerializer.Deserialize<Dictionary<string,Dictionary<int,Dictionary<string,DiabloInfusionState.FieldState>>>>(File.ReadAllText(statePath))!;
  var originals=JsonSerializer.Deserialize<Dictionary<string,Dictionary<int,Dictionary<string,DiabloInfusionState.FieldState>>>>(File.ReadAllText(Path.Combine(baseline,DiabloInfusionState.Filename)))!;
  int count=0;
  foreach(var (id,fields) in states["EquipParamWeapon"]){
   if(!before.TryGetValue(id,out var original)||!current.TryGetValue(id,out var live))continue;
   foreach(string name in new[]{"spEffectMsgId0","spEffectMsgId1","spEffectMsgId2"}){
    if(fields.ContainsKey(name))continue;
    var value=JsonSerializer.SerializeToElement(ParamHelper.FindCell(original,name)!.Value);
    if(originals["EquipParamWeapon"].TryGetValue(id,out var old)&&old.TryGetValue(name,out var recorded))value=recorded.Original;
    fields[name]=new(){Original=value,Applied=JsonSerializer.SerializeToElement(ParamHelper.FindCell(live,name)!.Value)};count++;
   }
  }
  File.WriteAllText(statePath,JsonSerializer.Serialize(states,options));Console.WriteLine($"Migrated {count} missing passive UI originals from retained pre-refinement PARAM/state.");
 }
 public static void Run(string root,string baseline,string target,string game,string report)
 {
  SoulsFormats.Oodle.Oodle6Ptr=System.Runtime.InteropServices.NativeLibrary.Load(Path.Combine(game,"oo2core_6_win64.dll"));
  var original=RegulationDecryptor.DecryptERRegulation(Path.Combine(baseline,"regulation.bin"));var final=RegulationDecryptor.DecryptERRegulation(target);
  PARAM Load(BND4 bnd,string name){var param=PARAM.Read(bnd.Files.Single(f=>f.Name.EndsWith(name+".param",StringComparison.OrdinalIgnoreCase)).Bytes);
   param.ApplyParamdefSomewhatCarefully(PARAMDEF.XmlDeserialize(Path.Combine(root,"tools/vendor/Paramdex/ER/Defs",name+".xml"),false,false));return param;}
  int checks=0,texts=0,prices=0;void Check(bool ok,string message){checks++;if(!ok)throw new InvalidDataException(message);}
  var armor=Load(final,"EquipParamProtector").Rows.Where(r=>r.Name?.Contains("[LootForge]")==true).ToArray();
  var equipment=new[]{"EquipParamWeapon","EquipParamProtector","EquipParamAccessory"}.ToDictionary(n=>n,n=>Load(final,n).Rows.ToDictionary(r=>r.ID));
  foreach(var row in armor){
   Check(DiabloBalanceService.FlatArmorFields.All(f=>ParamHelper.GetCellInt(row,f)==0),"Nonzero obsolete armor defense "+row.ID);
   Check(DiabloBalanceService.ArmorRateFields.All(f=>Convert.ToDouble(ParamHelper.FindCell(row,f)!.Value)>=0.75&&Convert.ToDouble(ParamHelper.FindCell(row,f)!.Value)<=1),"Armor negation bound "+row.ID);
  }
  var values=new List<int>();var sells=new List<int>();
  foreach(var table in equipment.Values)foreach(var row in table.Values.Where(r=>r.Name?.Contains("[LootForge]")==true)){
   int buy=ParamHelper.GetCellInt(row,"saleValue"),sell=ParamHelper.GetCellInt(row,"sellValue");values.Add(buy);sells.Add(sell);
   Check(buy>=300&&buy<=12000&&sell<=500&&sell<=buy*0.06,"Inflated generated equipment price "+row.ID);
  }
  using var history=JsonDocument.Parse(File.ReadAllText(Path.Combine(baseline,"lootforge_diablo_texts.json")));
  foreach(var archive in history.RootElement.EnumerateObject()){
   string relative=archive.Name.Replace('/',Path.DirectorySeparatorChar);
   var sourceArchive=BND4.Read(Path.Combine(baseline,"msg",relative));var targetArchive=BND4.Read(Path.Combine(Path.GetDirectoryName(target)!,"msg",relative));
   foreach(var file in archive.Value.EnumerateObject()){
    var sourceFile=sourceArchive.Files.First(f=>Path.GetFileName(f.Name)==file.Name);var targetFile=targetArchive.Files.First(f=>Path.GetFileName(f.Name)==file.Name);
    var before=FMG.Read(sourceFile.Bytes).Entries.ToDictionary(e=>e.ID,e=>e.Text);var after=FMG.Read(targetFile.Bytes).Entries.ToDictionary(e=>e.ID,e=>e.Text);
    foreach(var entry in file.Value.EnumerateObject()){
     int id=int.Parse(entry.Name);var state=entry.Value;bool present=before.TryGetValue(id,out var text);
     bool tracked=present==state.GetProperty("AppliedExists").GetBoolean()&&text==state.GetProperty("Applied").GetString();
     bool expectedExists=tracked?state.GetProperty("OriginalExists").GetBoolean():present;
     string? expected=tracked?state.GetProperty("Original").GetString():text;
     Check(after.TryGetValue(id,out var restored)==expectedExists&&restored==expected,$"Vanilla text was replaced: {archive.Name}/{file.Name}:{id}");texts++;
    }
   }
  }
  using var fields=JsonDocument.Parse(File.ReadAllText(Path.Combine(baseline,"lootforge_diablo_fields.json")));
  foreach(var table in fields.RootElement.EnumerateObject()){
   var originals=Load(original,table.Name).Rows.ToDictionary(r=>r.ID);
   foreach(var item in table.Value.EnumerateObject())foreach(var field in item.Value.EnumerateObject().Where(f=>f.Name is "saleValue" or "sellValue" or "basicPrice")){
    int id=int.Parse(item.Name);if(!originals.TryGetValue(id,out var before)||!equipment[table.Name].TryGetValue(id,out var after))continue;
    string current=JsonSerializer.SerializeToElement(ParamHelper.FindCell(before,field.Name)!.Value).ToString();
    string expected=current==field.Value.GetProperty("Applied").ToString()?field.Value.GetProperty("Original").ToString():current;
    Check(JsonSerializer.SerializeToElement(ParamHelper.FindCell(after,field.Name)!.Value).ToString()==expected,"Vanilla economy changed: "+id);prices++;
   }
  }
  File.WriteAllText(report,JsonSerializer.Serialize(new{checks,restoredOrPreservedVanillaTexts=texts,restoredVanillaPriceFields=prices,armor=armor.Length,
   generatedBuy=new{min=values.Min(),max=values.Max(),average=values.Average()},generatedSell=new{min=sells.Min(),max=sells.Max(),average=sells.Average()}},new JsonSerializerOptions{WriteIndented=true}));
  Console.WriteLine($"PASS {checks} refinement checks; {texts} vanilla texts; {prices} native prices; {armor.Length} armor pieces.");
 }
}
