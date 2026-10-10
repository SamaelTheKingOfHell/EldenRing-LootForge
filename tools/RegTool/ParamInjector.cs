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
    }
}
