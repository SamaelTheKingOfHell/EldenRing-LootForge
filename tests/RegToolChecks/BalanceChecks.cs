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
        DiabloBalanceService.Apply(blade,"EquipParamWeapon",1,0.18,200);
        check(ParamHelper.GetCellInt(blade,"attackBasePhysics")+ParamHelper.GetCellInt(blade,"attackBaseMagic")<=224,
            "starter imported split damage obeys a bound relative to its native class/template");
        var vanilla=Add(weapon,2020000);DiabloEffectService.Set(vanilla,"attackBasePhysics",500);
        DiabloBalanceService.Apply(vanilla,"EquipParamWeapon",1,0.18);
        check(ParamHelper.GetCellInt(vanilla,"attackBasePhysics")==500,"imported base-power bounds preserve host originals");
        var armor=Table("EquipParamProtector");var chest=Add(armor,100000100);
        DiabloEffectService.Set(chest,"protectorCategory",1);DiabloEffectService.Set(chest,"neutralDamageCutRate",0.4f);
        DiabloEffectService.Set(chest,"magicDamageCutRate",0.97f);
        DiabloBalanceService.Apply(chest,"EquipParamProtector",1,0.18);
        check(Math.Abs(Convert.ToSingle(ParamHelper.FindCell(chest,"neutralDamageCutRate")!.Value)-0.84f)<0.001,
            "starter body armor absorption is bounded at sixteen percent");
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
        var katana=Add(weapon,100000200);DiabloEffectService.Set(katana,"attackBasePhysics",115);
        var bleed=Add(effects,6400);DiabloEffectService.Set(bleed,"bloodAttackPower",45);
        DiabloEffectService.Set(katana,"spEffectBehaviorId0",6400);DiabloEffectService.Set(katana,"spEffectMsgId0",6501);
        using var legendary=JsonDocument.Parse("[{\"param_table\":\"EquipParamWeapon\",\"new_param_id\":100000200,\"field_updates\":{\"_lf_diablo_power\":0.207,\"_lf_diablo_tier\":1,\"_lf_diablo_stat_deltas\":{\"attackBasePhysics\":20,\"attackBaseFire\":35},\"_lf_diablo_on_hit\":[{\"id\":6400,\"msg_id\":6501,\"power\":0.5}]}}]");
        service.Apply(legendary.RootElement);
        check(ParamHelper.GetCellInt(katana,"attackBasePhysics")>=115&&DiabloBalanceService.TotalAttack(katana)>115,
            "early legendary katana preserves Uchigatana physical damage while adding bounded bonuses");
        check(ParamHelper.GetCellInt(katana,"spEffectBehaviorId0")==6400&&ParamHelper.GetCellInt(bleed,"bloodAttackPower")==45,
            "rolled buildup never replaces or scales away inherited Uchigatana bleed");
        var addedBleed=effects.Rows.Single(row=>row.ID==ParamHelper.GetCellInt(katana,"spEffectBehaviorId1"));
        check(ParamHelper.GetCellInt(addedBleed,"bloodAttackPower")>=22&&ParamHelper.GetCellInt(katana,"spEffectMsgId0")==6501,
            "added status has useful nonzero buildup and preserves the native passive UI entry");
        using var passiveMessage=JsonDocument.Parse("[{\"param_table\":\"EquipParamWeapon\",\"new_param_id\":100000200,\"field_updates\":{\"_lf_diablo_messages\":[1002]}}]");
        service.Apply(passiveMessage.RootElement);
        check(ParamHelper.GetCellInt(katana,"spEffectMsgId0")==6501&&ParamHelper.GetCellInt(katana,"spEffectMsgId1")==1002,
            "non-status passive UI appends after original bleed instead of overwriting it");
        tables["EquipParamProtector"]=armor;
        var brokenArmor=Add(armor,100000300);DiabloEffectService.Set(brokenArmor,"protectorCategory",1);
        using var armorSpec=JsonDocument.Parse("[{\"param_table\":\"EquipParamProtector\",\"new_param_id\":100000300,\"field_updates\":{\"_lf_diablo_power\":0.207,\"_lf_diablo_tier\":1,\"_lf_diablo_stat_deltas\":{\"defensePhysics\":15}}}]");
        service.Apply(armorSpec.RootElement);
        check(DiabloBalanceService.FlatArmorFields.All(field=>ParamHelper.GetCellInt(brokenArmor,field)==0)&&
            Convert.ToDouble(ParamHelper.FindCell(brokenArmor,"neutralDamageCutRate")!.Value)<1,
            "all-100 schema armor defaults become zero flat defense with real native negation bonuses");
        var economy=new EquipmentPricingService(Load);economy.Apply(legendary.RootElement);
        int earlyPrice=ParamHelper.GetCellInt(katana,"saleValue");
        using var laterLabel=JsonDocument.Parse("[{\"param_table\":\"EquipParamWeapon\",\"new_param_id\":100000200,\"field_updates\":{\"_lf_diablo_tier\":4}}]");
        economy.Apply(laterLabel.RootElement);
        check(earlyPrice==ParamHelper.GetCellInt(katana,"saleValue"),"finalized identical strength costs the same in early and endgame regions");
        DiabloEffectService.Set(katana,"attackBasePhysics",200);economy.Apply(laterLabel.RootElement);
        check(ParamHelper.GetCellInt(katana,"saleValue")>earlyPrice&&ParamHelper.GetCellInt(katana,"sellValue")<=500,
            "stronger finalized equipment costs more while rune sale returns remain bounded");
    }
}
