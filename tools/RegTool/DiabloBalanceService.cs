using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Native armor negation and weapon-relative bounds; never an absolute starter damage ceiling.</summary>
public static class DiabloBalanceService
{
    public static readonly string[] AttackFields = {"attackBasePhysics","attackBaseMagic","attackBaseFire","attackBaseThunder","attackBaseDark"};
    public static readonly string[] ArmorRateFields = {"neutralDamageCutRate","slashDamageCutRate","blowDamageCutRate","thrustDamageCutRate","magicDamageCutRate","fireDamageCutRate","thunderDamageCutRate","darkDamageCutRate"};
    public static readonly string[] FlatArmorFields = {"defensePhysics","defenseSlash","defenseBlow","defenseThrust","defenseMagic","defenseFire","defenseThunder","defenseDark"};
    static readonly Dictionary<string,string> RateForFlat = FlatArmorFields.Zip(ArmorRateFields).ToDictionary(pair=>pair.First,pair=>pair.Second);

    public static double TotalAttack(PARAM.Row row) => AttackFields.Sum(field=>Convert.ToDouble(ParamHelper.FindCell(row,field)!.Value));
    public static bool ArmorDelta(PARAM.Row row,string field,double amount)
    {
        if (RateForFlat.TryGetValue(field,out var rate))
        {
            // Flat-defense affix points represent tenths of a percentage point of
            // armor negation. Retail armor's flat defense fields remain zero.
            double current=Convert.ToDouble(ParamHelper.FindCell(row,rate)!.Value);
            DiabloEffectService.Set(row,rate,Math.Clamp(current-Math.Clamp(amount*0.001,-0.03,0.03),0.65,1));
            return true;
        }
        if(field is "poise" or "toughnessCorrectRate")
        {
            var cell=ParamHelper.FindCell(row,"toughnessCorrectRate")!;
            DiabloEffectService.Set(row,"toughnessCorrectRate",Convert.ToDouble(cell.Value)+amount*0.001);
            return true;
        }
        return false;
    }
    public static void Apply(PARAM.Row row,string table,int tier,double power,double baseAttack=0,IReadOnlyDictionary<string,double>? baseDamage=null)
    {
        if(row.ID<100000000)return;
        tier=Math.Clamp(tier,1,4);
        if(table=="EquipParamWeapon"&&baseAttack>0)
        {
            double total=TotalAttack(row);
            double ceiling=baseAttack*(1.08+Math.Clamp(power,0,2)*0.20);
            // Preserve the class/template's native damage, scaling and requirements.
            if(total>ceiling)
                foreach(string field in AttackFields)
                {
                    double original=Convert.ToDouble(ParamHelper.FindCell(row,field)!.Value);
                    double baseline=baseDamage?.GetValueOrDefault(field)??0;
                    double value=baseDamage==null?original*ceiling/total:
                        baseline+Math.Max(0,original-baseline)*Math.Max(0,ceiling-baseAttack)/Math.Max(1,total-baseAttack);
                    DiabloEffectService.Set(row,field,original>0?Math.Max(baseline,Math.Max(1,Math.Round(value))):0);
                }
        }
        if(table=="EquipParamProtector")
        {
            foreach(string field in FlatArmorFields)DiabloEffectService.Set(row,field,0);
            int slot=Math.Clamp(ParamHelper.GetCellInt(row,"protectorCategory"),0,3);
            double absorption=new[]{0.06,0.16,0.05,0.095}[slot]+(tier-1)*new[]{0.005,0.02,0.005,0.01}[slot];
            foreach(string field in ArmorRateFields)
                DiabloEffectService.Set(row,field,Math.Clamp(Convert.ToDouble(ParamHelper.FindCell(row,field)!.Value),1-absorption,1));
            double poiseCap=new[]{0.012,0.045,0.009,0.025}[slot];
            var poise=ParamHelper.FindCell(row,"toughnessCorrectRate")!;
            DiabloEffectService.Set(row,"toughnessCorrectRate",Math.Clamp(Convert.ToDouble(poise.Value),0,poiseCap));
        }
    }
}
