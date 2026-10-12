using System;
using System.Collections.Generic;
using System.Text.Json;
using SoulsFormats;

namespace LootForge.RegTool
{
    /// <summary>
    /// Unified facade delegating equipment and loot parameter injection to specialized services.
    /// Preserves existing API signature while maintaining [CS-MODULAR] and [CS-GRANULARITY].
    /// </summary>
    public static class ParamInjector
    {
        public static void InjectEquipParams(
            JsonElement equipParamsEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, int> itemIdToVanillaSourceId,
            ref int injectedEquipCount)
        {
            EquipInjector.InjectEquipParams(
                equipParamsEl,
                getOrLoadParam,
                itemIdToIsProtector,
                itemIdToIsWeapon,
                itemIdToVanillaSourceId,
                ref injectedEquipCount
            );
        }

        public static void InjectLootDistribution(
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            ref int injectedLootCount)
        {
            LootInjector.InjectLootDistribution(
                lootEl,
                getOrLoadParam,
                itemIdToIsProtector,
                itemIdToIsWeapon,
                ref injectedLootCount
            );
        }

        public static void PurgePreviousInjections(
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam)
        {
            // 1. Purge synthetic rows and clear mod items from existing rows in ItemLotParam_enemy
            try
            {
                var (itemLotParam, _) = getOrLoadParam("ItemLotParam_enemy", "ItemLotParam");
                itemLotParam.Rows.RemoveAll(r => (r.Name != null && r.Name.Contains("[LootForge]")) || (r.ID >= 9100000 && r.ID < 9200000));

                foreach (var row in itemLotParam.Rows)
                {
                    for (int s = 1; s <= 8; s++)
                    {
                        int itemId = ParamHelper.GetCellInt(row, $"lotItemId0{s}");
                        if (itemId >= 9000000 && itemId < 10000000)
                        {
                            ParamHelper.SetCellIfExists(row, $"lotItemId0{s}", 0);
                            ParamHelper.SetCellIfExists(row, $"lotItemCategory0{s}", 0);
                            ParamHelper.SetCellIfExists(row, $"lotItemBasePoint0{s}", (ushort)0);
                            ParamHelper.SetCellIfExists(row, $"lotItemNum0{s}", (byte)0);
                            ParamHelper.SetCellIfExists(row, $"getItemFlagId0{s}", 0u);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge ItemLotParam_enemy: {ex.Message}");
            }

            // 1b. Purge synthetic rows and clear mod items from existing rows in ItemLotParam_map
            try
            {
                var (mapLotParam, _) = getOrLoadParam("ItemLotParam_map", "ItemLotParam");
                mapLotParam.Rows.RemoveAll(r => (r.Name != null && r.Name.Contains("[LootForge]")) || (r.ID >= 9100000 && r.ID < 9200000));

                foreach (var row in mapLotParam.Rows)
                {
                    for (int s = 1; s <= 8; s++)
                    {
                        int itemId = ParamHelper.GetCellInt(row, $"lotItemId0{s}");
                        if (itemId >= 9000000 && itemId < 10000000)
                        {
                            ParamHelper.SetCellIfExists(row, $"lotItemId0{s}", 0);
                            ParamHelper.SetCellIfExists(row, $"lotItemCategory0{s}", 0);
                            ParamHelper.SetCellIfExists(row, $"lotItemBasePoint0{s}", (ushort)0);
                            ParamHelper.SetCellIfExists(row, $"lotItemNum0{s}", (byte)0);
                            ParamHelper.SetCellIfExists(row, $"getItemFlagId0{s}", 0u);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge ItemLotParam_map: {ex.Message}");
            }

            // 2. Purge LootForge rows in ShopLineupParam
            try
            {
                var (shopParam, _) = getOrLoadParam("ShopLineupParam", "ShopLineupParam");
                shopParam.Rows.RemoveAll(r =>
                    (r.Name != null && r.Name.Contains("[LootForge]")) ||
                    (ParamHelper.GetCellInt(r, "equipId") >= 9000000 && ParamHelper.GetCellInt(r, "equipId") < 10000000));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge ShopLineupParam: {ex.Message}");
            }

            // 3. Purge LootForge rows in EquipParamWeapon
            try
            {
                var (weaponParam, _) = getOrLoadParam("EquipParamWeapon", "EquipParamWeapon");
                weaponParam.Rows.RemoveAll(r =>
                    (r.ID >= 9000000 && r.ID < 10000000) ||
                    (r.Name != null && r.Name.Contains("[LootForge]")));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge EquipParamWeapon: {ex.Message}");
            }

            // 4. Purge LootForge rows in EquipParamProtector
            try
            {
                var (protectorParam, _) = getOrLoadParam("EquipParamProtector", "EquipParamProtector");
                protectorParam.Rows.RemoveAll(r =>
                    (r.ID >= 9000000 && r.ID < 10000000) ||
                    (r.Name != null && r.Name.Contains("[LootForge]")));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge EquipParamProtector: {ex.Message}");
            }

            // 5. Purge LootForge rows in SpEffectParam
            try
            {
                var (spEffectParam, _) = getOrLoadParam("SpEffectParam", "SpEffectParam");
                spEffectParam.Rows.RemoveAll(r =>
                    (r.ID >= 9000000 && r.ID < 10000000) ||
                    (r.Name != null && r.Name.Contains("[LootForge]")));
            }
            catch {}
        }
    }
}
