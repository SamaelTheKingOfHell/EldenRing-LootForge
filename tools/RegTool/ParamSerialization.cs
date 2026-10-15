using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Serialize parameter rows in the order required by runtime ID lookup.</summary>
public static class ParamSerialization
{
    /// <summary>Sort explicit row IDs before writing; SoulsFormats preserves the incoming list order.</summary>
    public static byte[] Write(PARAM param)
    {
        if (!param.HeaderlessRows) param.Rows.Sort((left, right) => left.ID.CompareTo(right.ID));
        return param.Write();
    }
}
