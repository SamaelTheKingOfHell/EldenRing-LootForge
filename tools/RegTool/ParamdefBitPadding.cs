using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Represent undocumented bits explicitly so reading/writing preserves them.</summary>
public static class ParamdefBitPadding
{
    public static PARAMDEF Preserve(PARAMDEF def)
    {
        var fields = new List<PARAMDEF.Field>();
        int used = 0, limit = 0, serial = 0;
        PARAMDEF.DefType type = PARAMDEF.DefType.u8;
        void Finish()
        {
            if (used > 0 && used < limit)
                fields.Add(new PARAMDEF.Field(def, type, $"_lf_preserved_bits_{serial++}") { BitSize = limit - used });
            used = limit = 0;
        }
        foreach (var field in def.Fields)
        {
            int width = field.DisplayType switch
            {
                PARAMDEF.DefType.u8 or PARAMDEF.DefType.s8 or PARAMDEF.DefType.dummy8 => 8,
                PARAMDEF.DefType.u16 or PARAMDEF.DefType.s16 => 16,
                PARAMDEF.DefType.u32 or PARAMDEF.DefType.s32 => 32,
                _ => 0
            };
            if (field.BitSize < 0 || width != limit || used + field.BitSize > limit) Finish();
            fields.Add(field);
            if (field.BitSize >= 0)
            {
                limit = width;
                type = field.DisplayType;
                used += field.BitSize;
                if (used == limit) Finish();
            }
        }
        Finish();
        def.Fields = fields;
        return def;
    }
}
