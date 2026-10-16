using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;
using LootForge.RegTool;

/// <summary>Read-only equipment and effect values from actual encrypted regulations.</summary>
public static class RefinementAudit
{
 public static void Run(string root,string source,string game,string output)
 {
  SoulsFormats.Oodle.Oodle6Ptr=System.Runtime.InteropServices.NativeLibrary.Load(Path.Combine(game,"oo2core_6_win64.dll"));
  var binder=RegulationDecryptor.DecryptERRegulation(source);
  PARAM Load(string table,string? def=null){
   var param=PARAM.Read(binder.Files.Single(f=>f.Name.EndsWith(table+".param",StringComparison.OrdinalIgnoreCase)).Bytes);
   var definition=PARAMDEF.XmlDeserialize(Path.Combine(root,"tools/vendor/Paramdex/ER/Defs",(def??table)+".xml"),false,false);
   if(table=="SpEffectParam")ParamdefBitPadding.Preserve(definition);
   param.ApplyParamdefSomewhatCarefully(definition);return param;
  }
  var weapons=Load("EquipParamWeapon");var armor=Load("EquipParamProtector");var effects=Load("SpEffectParam","SpEffect");
  object Values(PARAM.Row row)=>new{row.ID,row.Name,fields=row.Cells.Where(c=>c.Def.InternalName.StartsWith("defense")||c.Def.InternalName.EndsWith("DamageCutRate")||c.Def.InternalName.StartsWith("resist")||c.Def.InternalName.StartsWith("attackBase")||c.Def.InternalName.StartsWith("spEffect")||c.Def.InternalName.StartsWith("residentSpEffect")||c.Def.InternalName is "sellValue" or "saleValue" or "basicPrice" or "equipModelId" or "protectorCategory" or "toughnessCorrectRate" or "weight").ToDictionary(c=>c.Def.InternalName,c=>c.Value)};
  bool Owned(PARAM.Row row)=>row.Name?.Contains("[LootForge]")==true;
  var report=new{source,armor=armor.Rows.Where(Owned).Select(Values),referenceArmor=armor.Rows.Where(r=>!Owned(r)&&r.ID>=10000&&r.ID<100000).Take(16).Select(Values),
   referenceWeapons=weapons.Rows.Where(r=>r.ID is 9000000 or 9010000 or 2020000).Select(Values),weapons=weapons.Rows.Where(Owned).Take(18).Select(Values),
   effects=effects.Rows.Where(r=>r.ID is 6400 or 6410 or 6420 or 6500 or 6600 || r.Name?.StartsWith("[LootForge] Diablo Scaled")==true).Take(25)
    .Select(r=>new{r.ID,r.Name,fields=r.Cells.Where(c=>c.Def.InternalName.EndsWith("AttackPower")||c.Def.InternalName.Contains("maxHp")||c.Def.InternalName is "changeHpPoint" or "itemDropRate" or "physicsDiffenceRate").ToDictionary(c=>c.Def.InternalName,c=>c.Value)})};
  File.WriteAllText(output,JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true}));
 }
}
