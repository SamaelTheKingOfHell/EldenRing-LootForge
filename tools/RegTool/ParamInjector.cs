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
            Dictionary<int, bool> itemIdToIsAccessory,
            Dictionary<int, int> itemIdToVanillaSourceId,
            ref int injectedEquipCount)
        {
            EquipInjector.InjectEquipParams(
                equipParamsEl,
                getOrLoadParam,
                itemIdToIsProtector,
                itemIdToIsWeapon,
                itemIdToVanillaSourceId,
                ref injectedEquipCount,
                itemIdToIsAccessory
            );
        }

        public static void InjectLootDistribution(
            JsonElement lootEl,
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Dictionary<int, bool> itemIdToIsProtector,
            Dictionary<int, bool> itemIdToIsWeapon,
            Dictionary<int, bool> itemIdToIsAccessory,
            ref int injectedLootCount)
        {
            LootInjector.InjectLootDistribution(
                lootEl,
                getOrLoadParam,
                itemIdToIsProtector,
                itemIdToIsWeapon,
                itemIdToIsAccessory,
                ref injectedLootCount
            );
        }

        public static void PurgePreviousInjections(
            Func<string, string, (PARAM Param, BinderFile File)> getOrLoadParam,
            Action<string, string>? purgeNamedRows = null)
        {
            var allLfItemIds = new HashSet<int>();

            // 1. Identify and purge LootForge rows in EquipParamWeapon
            try
            {
                var (weaponParam, _) = getOrLoadParam("EquipParamWeapon", "EquipParamWeapon");
                foreach (var r in weaponParam.Rows)
                {
                    if (r.Name != null && r.Name.Contains("[LootForge]"))
                    {
                        allLfItemIds.Add(r.ID);
                    }
                }
                weaponParam.Rows.RemoveAll(r => r.Name != null && r.Name.Contains("[LootForge]"));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge EquipParamWeapon: {ex.Message}");
            }

            // 2. Identify and purge LootForge rows in EquipParamProtector
            try
            {
                var (protectorParam, _) = getOrLoadParam("EquipParamProtector", "EquipParamProtector");
                foreach (var r in protectorParam.Rows)
                {
                    if (r.Name != null && r.Name.Contains("[LootForge]"))
                    {
                        allLfItemIds.Add(r.ID);
                    }
                }
                protectorParam.Rows.RemoveAll(r => r.Name != null && r.Name.Contains("[LootForge]"));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge EquipParamProtector: {ex.Message}");
            }

            // 3. Identify and purge LootForge rows in EquipParamAccessory
            try
            {
                var (accessoryParam, _) = getOrLoadParam("EquipParamAccessory", "EquipParamAccessory");
                foreach (var r in accessoryParam.Rows)
                {
                    if (r.Name != null && r.Name.Contains("[LootForge]"))
                    {
                        allLfItemIds.Add(r.ID);
                    }
                }
                accessoryParam.Rows.RemoveAll(r => r.Name != null && r.Name.Contains("[LootForge]"));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge EquipParamAccessory: {ex.Message}");
            }

            // 4. Purge LootForge rows in SpEffectParam
            try
            {
                if (purgeNamedRows != null) purgeNamedRows("SpEffectParam", "SpEffect");
                else
                {
                    var (spEffectParam, _) = getOrLoadParam("SpEffectParam", "SpEffect");
                    spEffectParam.Rows.RemoveAll(r => r.Name != null && r.Name.Contains("[LootForge]"));
                }
            }
            catch {}

            // 5. Purge synthetic rows and clear mod items from existing rows in ItemLotParam_enemy
            try
            {
                var (itemLotParam, _) = getOrLoadParam("ItemLotParam_enemy", "ItemLotParam");
                itemLotParam.Rows.RemoveAll(r => r.Name != null && r.Name.Contains("[LootForge]"));

                foreach (var row in itemLotParam.Rows)
                {
                    for (int s = 1; s <= 8; s++)
                    {
                        int itemId = ParamHelper.GetCellInt(row, $"lotItemId0{s}");
                        if (allLfItemIds.Contains(itemId))
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

            // 6. Purge synthetic rows and clear mod items from existing rows in ItemLotParam_map
            try
            {
                var (mapLotParam, _) = getOrLoadParam("ItemLotParam_map", "ItemLotParam");
                mapLotParam.Rows.RemoveAll(r => r.Name != null && r.Name.Contains("[LootForge]"));

                foreach (var row in mapLotParam.Rows)
                {
                    for (int s = 1; s <= 8; s++)
                    {
                        int itemId = ParamHelper.GetCellInt(row, $"lotItemId0{s}");
                        if (allLfItemIds.Contains(itemId))
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

            // 7. Purge LootForge rows in ShopLineupParam
            try
            {
                var (shopParam, _) = getOrLoadParam("ShopLineupParam", "ShopLineupParam");
                shopParam.Rows.RemoveAll(r =>
                    (r.Name != null && r.Name.Contains("[LootForge]")) ||
                    allLfItemIds.Contains(ParamHelper.GetCellInt(r, "equipId")));
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[RegTool WARN] Could not purge ShopLineupParam: {ex.Message}");
            }

            // 8. Purge LootForge custom skills and moveset behaviors
            SkillMovesetService.PurgePreviousInjections(getOrLoadParam, purgeNamedRows);
        }
    }
}
