using System.Text.Json;
using LootForge.RegTool;
using SoulsFormats;

/// <summary>Starter bounds and inherited native passives, including the discovery flood regression.</summary>
public static class BalanceChecks
{
    public static void Run(string defs, Action<bool,string> check)
    {
        PARAM Table(string name)
        {
            var def=PARAMDEF.XmlDeserialize(Path.Combine(defs,name+".xml"),false,false);
            var table=new PARAM{ParamType=def.ParamType,Rows=new()};table.ApplyParamdef(def);return table;
        }
        PARAM.Row Add(PARAM table,int id)
        {
            var row=new PARAM.Row(id,"Fixture",table.AppliedParamdef);table.Rows.Add(row);return row;
        }
        var weapon=Table("EquipParamWeapon");var blade=Add(weapon,100000000);
        DiabloEffectService.Set(blade,"attackBasePhysics",300);DiabloEffectService.Set(blade,"attackBaseMagic",200);
        DiabloBalanceService.Apply(blade,"EquipParamWeapon",1,0.18);
        check(ParamHelper.GetCellInt(blade,"attackBasePhysics")+ParamHelper.GetCellInt(blade,"attackBaseMagic")<=123,
            "starter imported split damage obeys one combined regional bound");
        var vanilla=Add(weapon,2020000);DiabloEffectService.Set(vanilla,"attackBasePhysics",500);
        DiabloBalanceService.Apply(vanilla,"EquipParamWeapon",1,0.18);
        check(ParamHelper.GetCellInt(vanilla,"attackBasePhysics")==500,"imported base-power bounds preserve host originals");
        var armor=Table("EquipParamProtector");var chest=Add(armor,100000100);
        DiabloEffectService.Set(chest,"protectorCategory",1);DiabloEffectService.Set(chest,"neutralDamageCutRate",0.4f);
        DiabloEffectService.Set(chest,"magicDamageCutRate",0.97f);
        DiabloBalanceService.Apply(chest,"EquipParamProtector",1,0.18);
        check(Math.Abs(Convert.ToSingle(ParamHelper.FindCell(chest,"neutralDamageCutRate")!.Value)-0.86f)<0.001,
            "starter body armor absorption is bounded at fourteen percent");
        check(Math.Abs(Convert.ToSingle(ParamHelper.FindCell(chest,"magicDamageCutRate")!.Value)-0.97f)<0.001,
            "starter bounds preserve already weaker protection");
        var effects=Table("SpEffect");var passive=Add(effects,100);
        DiabloEffectService.Set(passive,"itemDropRate",200f);DiabloEffectService.Set(passive,"addStrengthStatus",10);
        DiabloEffectService.Set(blade,"residentSpEffectId",100);
        var tables=new Dictionary<string,PARAM>{{"EquipParamWeapon",weapon},{"SpEffectParam",effects},
            {"Bullet",Table("BulletParam")},{"BehaviorParam",Table("BehaviorParam")},{"SpEffectVfxParam",Table("SpEffectVfx")}};
        (PARAM,BinderFile) Load(string name,string definition)=>(tables[name],new BinderFile());
        var service=new DiabloEffectService(Load);
        using var spec=JsonDocument.Parse("[{\"param_table\":\"EquipParamWeapon\",\"new_param_id\":100000000,\"field_updates\":{\"_lf_diablo_power\":0.18,\"_lf_diablo_tier\":1}}]");
        service.Apply(spec.RootElement);
        var scaled=effects.Rows.Single(row=>row.ID==ParamHelper.GetCellInt(blade,"residentSpEffectId"));
        check(ParamHelper.GetCellInt(scaled,"itemDropRate")==36&&ParamHelper.GetCellInt(scaled,"addStrengthStatus")==2,
            "inherited discovery and attribute bonuses scale with starter potency");
        check(ParamHelper.GetCellInt(passive,"itemDropRate")==200&&ParamHelper.GetCellInt(passive,"addStrengthStatus")==10,
            "passive scaling clones effects without mutating shared native templates");
    }
}
