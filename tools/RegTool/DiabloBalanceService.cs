using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Bound imported starter equipment without reducing the host's original equipment stats.</summary>
public static class DiabloBalanceService
{
    public static void Apply(PARAM.Row row, string table, int tier, double power)
    {
        if (row.ID < 100000000) return;
        tier = Math.Clamp(tier,1,4);
        if (table == "EquipParamWeapon")
        {
            string[] fields = {"attackBasePhysics","attackBaseMagic","attackBaseFire","attackBaseThunder","attackBaseDark"};
            double total = fields.Sum(field=>Convert.ToDouble(ParamHelper.FindCell(row,field)!.Value));
            double ceiling = new[]{120,190,270,340}[tier-1] * (1 + Math.Clamp(power,0,4)*0.1);
            if (total > ceiling)
                foreach (string field in fields)
                    DiabloEffectService.Set(row,field,Math.Floor(Convert.ToDouble(ParamHelper.FindCell(row,field)!.Value)*ceiling/total));
        }
        if (table == "EquipParamProtector" && tier == 1)
        {
            int slot = Math.Clamp(ParamHelper.GetCellInt(row,"protectorCategory"),0,3);
            double absorption = new[]{0.05,0.14,0.04,0.08}[slot];
            foreach (string field in new[]{"neutralDamageCutRate","slashDamageCutRate","blowDamageCutRate","thrustDamageCutRate","magicDamageCutRate","fireDamageCutRate","thunderDamageCutRate","darkDamageCutRate"})
            {
                var cell = ParamHelper.FindCell(row,field);
                if (cell != null) DiabloEffectService.Set(row,field,Math.Max(1-absorption,Convert.ToDouble(cell.Value)));
            }
        }
    }
}
