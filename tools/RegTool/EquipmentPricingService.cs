using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Value finalized native combat fields. Region, rarity labels and boss prestige have no price premium.</summary>
public sealed class EquipmentPricingService
{
    readonly Func<string,string,(PARAM Param,BinderFile File)> load;
    readonly Dictionary<string,Dictionary<int,PARAM.Row>> indices=new();
    readonly Dictionary<string,int> counts=new();
    public EquipmentPricingService(Func<string,string,(PARAM Param,BinderFile File)> load) { this.load=load; }
    Dictionary<int,PARAM.Row> Index(string name,string definition)
    {
        var table=load(name,definition).Param;
        if(!indices.TryGetValue(name,out var index))indices[name]=index=new();
        for(int i=counts.GetValueOrDefault(name);i<table.Rows.Count;i++)index[table.Rows[i].ID]=table.Rows[i];
        counts[name]=table.Rows.Count;return index;
    }
    public static double EffectPower(int id,Dictionary<int,PARAM.Row> effects,HashSet<int> visited)
    {
        if(id<=0||!visited.Add(id)||!effects.TryGetValue(id,out var row))return 0;
        double Value(string name)=>Convert.ToDouble(ParamHelper.FindCell(row,name)?.Value??0);
        double total=0;
        foreach(string field in new[]{"bloodAttackPower","poizonAttackPower","diseaseAttackPower","freezeAttackPower"})total+=Math.Max(0,Value(field))*5;
        foreach(string field in new[]{"maxHpRate","maxMpRate","maxStaminaRate","physicsAttackPowerRate","magicAttackPowerRate","fireAttackPowerRate","thunderAttackPowerRate","darkAttackPowerRate"})
        {double value=Value(field);if(value>1)total+=(value-1)*3000;}
        foreach(string field in new[]{"physicsDiffenceRate","magicDiffenceRate","fireDiffenceRate","thunderDiffenceRate","darkDiffenceRate"})
        {double value=Value(field);if(value>0&&value<1)total+=(1-value)*3000;}
        foreach(string field in new[]{"changeHpPoint","changeMpPoint"})total+=Math.Max(0,-Value(field))*40;
        total+=Math.Max(0,Value("staminaRecoverChangeSpeed"))*20+Math.Max(0,Value("itemDropRate"))*2;
        foreach(var cell in row.Cells.Where(c=>c.Def.InternalName.StartsWith("add")&&c.Def.InternalName.EndsWith("Status")))total+=Math.Max(0,Convert.ToDouble(cell.Value))*45;
        foreach(string link in new[]{"replaceSpEffectId","cycleOccurrenceSpEffectId","atkOccurrenceSpEffectId"})total+=EffectPower((int)Value(link),effects,visited);
        return Math.Min(2000,total);
    }
    public void Apply(System.Text.Json.JsonElement equipment)
    {
        var effects=Index("SpEffectParam","SpEffect");
        foreach(var ep in equipment.EnumerateArray())
        {
            if(ep.TryGetProperty("update_existing",out var update)&&update.GetBoolean())continue;
            string table=ep.GetProperty("param_table").GetString()!;
            int id=ep.GetProperty("new_param_id").GetInt32();
            var row=Index(table,table)[id];
            double Value(string field)=>Convert.ToDouble(ParamHelper.FindCell(row,field)?.Value??0);
            double score=150;
            if(table=="EquipParamWeapon")
            {
                score+=DiabloBalanceService.TotalAttack(row)*12;
                score+=new[]{"correctStrength","correctAgility","correctMagic","correctFaith","correctLuck"}.Sum(Value)*2;
                if(Value("swordArtsParamId")>0)score+=200;
            }
            else if(table=="EquipParamProtector")
            {
                score+=DiabloBalanceService.ArmorRateFields.Take(4).Average(field=>Math.Max(0,1-Value(field)))*5500;
                score+=DiabloBalanceService.ArmorRateFields.Skip(4).Average(field=>Math.Max(0,1-Value(field)))*3500;
                score+=Value("toughnessCorrectRate")*10000;
                score+=new[]{"resistPoison","resistDisease","resistBlood","resistCurse","resistFreeze","resistSleep","resistMadness"}.Sum(Value)*0.4;
            }
            var visited=new HashSet<int>();
            foreach(var cell in row.Cells.Where(c=>c.Def.InternalName.StartsWith("residentSpEffectId")||c.Def.InternalName.StartsWith("spEffectBehaviorId")||table=="EquipParamAccessory"&&c.Def.InternalName=="refId"))
                score+=EffectPower(Convert.ToInt32(cell.Value),effects,visited);
            double multiplier=1;
            if(ep.TryGetProperty("field_updates",out var fields))
            {
                if(fields.TryGetProperty("_lf_price_multiplier",out var mult))multiplier=mult.GetDouble();
                if(fields.TryGetProperty("_lf_diablo_proc",out var proc))score+=400*Math.Clamp(proc.GetProperty("power").GetDouble(),0,2);
            }
            int buy=(int)Math.Clamp(Math.Round(score*Math.Max(0,multiplier)/50)*50,300,12000);
            int sell=Math.Clamp((int)Math.Round(buy*0.05/5)*5,10,500);
            ParamHelper.SetCellIfExists(row,"saleValue",buy);ParamHelper.SetCellIfExists(row,"basicPrice",buy);ParamHelper.SetCellIfExists(row,"sellValue",sell);
        }
    }
}
