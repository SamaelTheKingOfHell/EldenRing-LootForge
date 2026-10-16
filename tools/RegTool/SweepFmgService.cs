using SoulsFormats;

namespace LootForge.RegTool;

/// <summary>Legacy sweep result contract; vanilla FMGs are deliberately preserved.</summary>
public static class SweepFmgService
{
    public record Effect(int ItemId,string Category,string Rarity,string Description);
    public static void Apply(BND4 archive,List<Effect> effects)
    {
        // Equipment infusion must never replace a vanilla name, caption or info.
        // Prior tracked text edits are restored by DiabloTextState on reforge.
    }
}
