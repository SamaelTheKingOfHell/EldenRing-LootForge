using System.Collections.Generic;

namespace LootForge.RegTool
{
    public enum EntityProgressionTier
    {
        Early = 1,
        Mid = 2,
        Late = 3,
        Endgame = 4
    }

    public record DiscoveredWeapon(
        int Id,
        int BaseId,
        string Name,
        int WepType,
        int SortId,
        int ReinforceTypeId,
        int ModelId,
        EntityProgressionTier Tier,
        bool IsBaseWeapon
    );

    public record DiscoveredProtector(
        int Id,
        string Name,
        int Category, // 0 = Head, 1 = Body, 2 = Arms, 3 = Legs
        string SlotName,
        int SortId,
        int ModelId,
        EntityProgressionTier Tier
    );

    public record DiscoveredAccessory(
        int Id,
        string Name,
        int SortId,
        int RefId,
        int IconId,
        EntityProgressionTier Tier
    );

    public record DiscoveredBossLot(
        int LotId,
        string Name,
        int RewardItemId,
        int RewardCategory,
        EntityProgressionTier Tier,
        bool IsMapTable = true,
        int FreeRows = 0,
        string Evidence = ""
    );

    public record DiscoveredChest(
        int LotId,
        string Name,
        int BaseItemId,
        int Category,
        EntityProgressionTier Tier,
        bool IsModded = false,
        int FreeRows = 0,
        string Evidence = ""
    );

    public record DiscoveredWorldSnapshot(
        int TotalWeapons,
        int BaseWeapons,
        int TotalProtectors,
        int TotalAccessories,
        int TotalBossLots,
        int TotalChests,
        List<DiscoveredWeapon> Weapons,
        List<DiscoveredProtector> Protectors,
        List<DiscoveredAccessory> Accessories,
        List<DiscoveredBossLot> BossLots,
        List<DiscoveredChest> Chests,
        List<ShopRangeCatalog.Shop>? Merchants = null,
        int SchemaVersion = 2,
        List<WorldLootCatalog.Destination>? Enemies = null
    );
}
