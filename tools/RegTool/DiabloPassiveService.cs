using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Clone native passive chains with useful nonzero values and unchanged shared templates.</summary>
public sealed class DiabloPassiveService
{
    readonly Func<Dictionary<int,PARAM.Row>> index;
    readonly Func<Dictionary<string,object>,string,PARAM.Row?,int> effect;
    readonly Dictionary<string,int> generated=new();
    public DiabloPassiveService(Func<Dictionary<int,PARAM.Row>> index,Func<Dictionary<string,object>,string,PARAM.Row?,int> effect)
    {this.index=index;this.effect=effect;}
    public int Scale(int id,double power,HashSet<int> path)
    {
        string key=$"passive:{id}:{power}";
        if(generated.TryGetValue(key,out int prior))return prior;
        if(!path.Add(id))throw new InvalidDataException($"Cyclic Diablo passive chain at {id}.");
        var rows=index();
        if(!rows.TryGetValue(id,out var source))throw new InvalidDataException($"Missing Diablo passive {id}.");
        var fields=new Dictionary<string,object>();
        foreach(var cell in source.Cells)
        {
            string name=cell.Def.InternalName;
            if(cell.Value is float number&&Convert.ToDouble(cell.Def.Default)==1&&name.EndsWith("Rate"))
                fields[name]=Math.Max(0.1,1+(number-1)*power);
            else if(name is "changeHpRate" or "changeMpRate" or "changeHpPoint" or "changeMpPoint" or "staminaRecoverChangeSpeed" or "bloodAttackPower" or "poizonAttackPower" or "diseaseAttackPower" or "freezeAttackPower" or "itemDropRate" ||
                (name.StartsWith("add")&&name.EndsWith("Status")) || (name.StartsWith("change")&&name.EndsWith("Point")&&!name.Contains("Equip")))
            {
                double original=Convert.ToDouble(cell.Value),scaled=original*power;
                if(cell.Value is not float)scaled=Math.Round(scaled);
                if(power>0&&original!=0&&Math.Abs(scaled)<1)scaled=Math.Sign(original);
                if(name.EndsWith("AttackPower")&&original>0&&power>0)scaled=Math.Max(15,scaled);
                fields[name]=scaled;
            }
        }
        string[] links={"replaceSpEffectId","cycleOccurrenceSpEffectId","atkOccurrenceSpEffectId"};
        foreach(string link in links)
        {
            int next=ParamHelper.GetCellInt(source,link);
            if(next>0&&next!=id)fields[link]=Scale(next,power,new(path));
        }
        int result=effect(fields,key,source);
        foreach(string link in links)if(ParamHelper.GetCellInt(source,link)==id)DiabloEffectService.Set(rows[result],link,result);
        generated[key]=result;return result;
    }
}
