using System.Text.Json;
using SoulsFormats;
using SoulsFormats.Cryptography;
using LootForge.RegTool;

// Exact-file acceptance checks. No source, target, asset, or save is modified.
string root=args[0],source=args[1],target=args[2],game=args[3],specsPath=args[4],reportPath=args[5];
string assetSource=args.Length>6?args[6]:source;
SoulsFormats.Oodle.Oodle6Ptr=System.Runtime.InteropServices.NativeLibrary.Load(Path.Combine(game,"oo2core_6_win64.dll"));
string defs=Path.Combine(root,"tools/vendor/Paramdex/ER/Defs");
var before=RegulationDecryptor.DecryptERRegulation(source);var after=RegulationDecryptor.DecryptERRegulation(target);
PARAM Load(BND4 binder,string name){
 var param=PARAM.Read(binder.Files.Single(f=>f.Name.EndsWith(name+".param",StringComparison.OrdinalIgnoreCase)).Bytes);
 param.ApplyParamdefSomewhatCarefully(PARAMDEF.XmlDeserialize(Path.Combine(defs,(name.StartsWith("ItemLot")?"ItemLotParam":name)+".xml"),false,false));return param;
}
int checks=0;void Check(bool ok,string message){checks++;if(!ok)throw new InvalidDataException(message);}
var tables=new[]{"EquipParamWeapon","EquipParamProtector","EquipParamAccessory","ItemLotParam_map","ItemLotParam_enemy","ShopLineupParam"}.ToDictionary(n=>n,n=>Load(after,n));
var indexes=tables.ToDictionary(p=>p.Key,p=>p.Value.Rows.ToDictionary(r=>r.ID));
foreach(var (name,param) in tables){Check(param.Rows.Count<=65535,name+" capacity");Check(param.Rows.Zip(param.Rows.Skip(1)).All(p=>p.First.ID<p.Second.ID),name+" sorted lookup");}
foreach(string name in new[]{"ItemLotParam_map","ItemLotParam_enemy"})
 foreach(var row in Load(before,name).Rows.Where(r=>r.Name?.Contains("[LootForge]")!=true))
  Check(indexes[name].TryGetValue(row.ID,out var next)&&JsonSerializer.Serialize(row.Cells.Select(c=>c.Value))==JsonSerializer.Serialize(next.Cells.Select(c=>c.Value)),name+" original changed: "+row.ID);
var world=WorldLootCatalog.Load(assetSource,game,defs,Load(before,"ItemLotParam_map"),Load(before,"ItemLotParam_enemy"),Load(before,"NpcParam"),Load(before,"ShopLineupParam"));
var allowedMap=world.Chests.Concat(world.Bosses).Select(i=>i.LotId).ToHashSet();var allowedEnemy=world.Enemies.Select(i=>i.LotId).ToHashSet();
var generated=new Dictionary<string,HashSet<int>>();var armorRoutes=new List<object>();var routes=new Dictionary<string,int>();
using var specs=JsonDocument.Parse(File.ReadAllText(specsPath));
foreach(var spec in specs.RootElement.EnumerateArray()){
 var equipment=spec.GetProperty("equip_params").EnumerateArray().Where(ep=>!ep.TryGetProperty("update_existing",out var existing)||!existing.GetBoolean()).ToArray();
 if(equipment.Length==0)continue;
 Check(spec.TryGetProperty("loot_distribution",out var loot),"Unrouted item");
 string kind=loot.GetProperty("source_kind").GetString()!;routes[kind]=routes.GetValueOrDefault(kind)+1;
 var awards=loot.GetProperty("awarded_items").EnumerateArray().Select(i=>i.GetInt32()).ToHashSet();bool shop=kind=="merchant";
 string dest=shop?"ShopLineupParam":loot.GetProperty("type").GetString()=="map_pickup"?"ItemLotParam_map":"ItemLotParam_enemy";
 int lot=shop?loot.GetProperty("range_start").GetInt32():int.Parse(loot.GetProperty("target_id").GetString()!);
 if(shop)Check(world.Merchants.Any(r=>r.Start==lot&&r.End==loot.GetProperty("range_end").GetInt32()),"Unopened vendor");
 else Check((dest=="ItemLotParam_map"?allowedMap:allowedEnemy).Contains(lot),"Unproven lot "+lot);
 foreach(var ep in equipment){
  string table=ep.GetProperty("param_table").GetString()!;int id=ep.GetProperty("new_param_id").GetInt32();
  Check(indexes[table].ContainsKey(id)&&awards.Contains(id),"Missing equipment or partial set "+id);
  if(!generated.ContainsKey(table))generated[table]=new();generated[table].Add(id);
  if(table=="EquipParamWeapon")Check(id%100==0,"Weapon reinforcement/name alias "+id);
  if(table=="EquipParamAccessory")Check(id>=20000&&id<60000,"Accessory namespace "+id);
  if(table=="EquipParamProtector"){
   int model=ParamHelper.GetCellInt(indexes[table][id],"equipModelId");
   int slot=Math.Clamp(ParamHelper.GetCellInt(indexes[table][id],"protectorCategory"),0,3);
   string prefix=new[]{"hd","bd","am","lg"}[slot];
   Check(Directory.EnumerateFiles(Path.Combine(Path.GetDirectoryName(assetSource)!,"parts"),$"{prefix}_*_{model:D4}.partsbnd.dcx").Any(),"Missing armor asset "+model);
  }
  if(shop){
   var rows=tables[dest].Rows.Where(r=>r.ID>=lot&&r.ID<=loot.GetProperty("range_end").GetInt32()&&ParamHelper.GetCellInt(r,"equipId")==id).ToArray();
   Check(rows.Length==1,"Unreachable vendor item "+id);int type=table=="EquipParamAccessory"?2:table=="EquipParamProtector"?1:0;
   Check(ParamHelper.GetCellInt(rows[0],"equipType")==type&&ParamHelper.GetCellInt(rows[0],"sellQuantity")==1&&ParamHelper.GetCellInt(rows[0],"eventFlag_forStock")>0,"Vendor category/stock "+id);
  }else{
   var rows=tables[dest].Rows.Where(r=>r.ID/10==lot/10&&ParamHelper.GetCellInt(r,"lotItemId01")==id&&r.Name?.Contains("[LootForge]")==true).ToArray();
   Check(rows.Length==1,"Unreachable reward "+id);int cat=table=="EquipParamAccessory"?4:table=="EquipParamProtector"?3:2;
   Check(ParamHelper.GetCellInt(rows[0],"lotItemCategory01")==cat,"ItemLot category "+id);
   if(dest=="ItemLotParam_map")Check(ParamHelper.GetCellInt(rows[0],"getItemFlagId")==ParamHelper.GetCellInt(indexes[dest][lot],"getItemFlagId"),"Acquisition flag "+id);
  }
 }
 if(equipment.Any(ep=>ep.GetProperty("param_table").GetString()=="EquipParamProtector"))armorRoutes.Add(new{set=spec.GetProperty("set_id").GetString(),kind,lot,pieces=equipment.Length});
}
int combatEvents=0;
string originalCommon=Path.Combine(Path.GetDirectoryName(source)!,"event/common.emevd.dcx");
string targetCommon=Path.Combine(Path.GetDirectoryName(target)!,"event/common.emevd.dcx");
if(File.Exists(originalCommon)&&File.Exists(targetCommon)){
 var originalScript=EMEVD.Read(originalCommon);var script=EMEVD.Read(targetCommon);
 bool Owned(long id)=>id>=DiabloCombatEvents.FirstEvent&&id<=DiabloCombatEvents.LastEvent;
 bool OwnedInit(EMEVD.Instruction ins)=>ins.Bank==2000&&ins.ID==0&&ins.ArgData.Length>=8&&Owned(BitConverter.ToUInt32(ins.ArgData,4));
 foreach(var ev in originalScript.Events.Where(ev=>!Owned(ev.ID))){
  var next=script.Events.Single(candidate=>candidate.ID==ev.ID);
  Check(ev.RestBehavior==next.RestBehavior,"Host event rest behavior "+ev.ID);
  Check(JsonSerializer.Serialize(ev.Instructions.Where(ins=>ev.ID!=0||!OwnedInit(ins)))==
   JsonSerializer.Serialize(next.Instructions.Where(ins=>ev.ID!=0||!OwnedInit(ins))),"Host event instructions "+ev.ID);
 }
 var ownedIds=script.Events.Where(ev=>Owned(ev.ID)).Select(ev=>ev.ID).ToArray();combatEvents=ownedIds.Length;
 var initIds=script.Events.Single(ev=>ev.ID==0).Instructions.Where(OwnedInit).Select(ins=>(long)BitConverter.ToUInt32(ins.ArgData,4)).Order().ToArray();
 Check(ownedIds.Order().SequenceEqual(initIds),"Generated combat events have exactly one initializer each");
}
int messageTables=0;
foreach(string path in Directory.EnumerateFiles(Path.Combine(Path.GetDirectoryName(target)!,"msg"),"item*.msgbnd.dcx",SearchOption.AllDirectories)){
 var archive=BND4.Read(path);
 foreach(var (table,ids) in generated){
  string category=table=="EquipParamWeapon"?"Weapon":table=="EquipParamProtector"?"Protector":"Accessory";
  foreach(string suffix in new[]{"Name","Caption","Info"})
   foreach(var file in archive.Files.Where(f=>FmgArchiveService.MatchesCategory(f.Name,category+suffix))){
    messageTables++;var entries=FMG.Read(file.Bytes).Entries.ToDictionary(e=>e.ID,e=>e.Text);
    foreach(int id in ids){Check(entries.TryGetValue(id,out var text)&&!string.IsNullOrWhiteSpace(text)&&!text.StartsWith('?'),"Unresolved FMG "+category+suffix+":"+id);
     if(suffix=="Caption")Check(text!.Split('\n').Length<=6,"Caption overlap "+id);}
   }
 }
}
File.WriteAllText(reportPath,JsonSerializer.Serialize(new{checks,generated=generated.ToDictionary(p=>p.Key,p=>p.Value.Count),routes,armorRoutes,messageTables,combatEvents},new JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine($"PASS: {checks} checks, {armorRoutes.Count} armor routes; generated rewards and FMGs resolve.");
