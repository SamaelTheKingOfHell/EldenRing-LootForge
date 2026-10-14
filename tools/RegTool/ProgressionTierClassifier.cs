namespace LootForge.RegTool
{
    /// <summary>
    /// Classifies world entities and loot drops into progression tiers based on IDs and landmark names.
    /// Adheres to [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
    /// </summary>
    public static class ProgressionTierClassifier
    {
        public static EntityProgressionTier ClassifyTier(int id, string? name)
        {
            string n = (name ?? "").ToLowerInvariant();

            // Early game landmarks
            if (id == 20330 || id == 1037420400 || n.Contains("groveside") || (n.Contains("beastman") && !n.Contains("dragonbarrow")))
                return EntityProgressionTier.Early;
            if (n.Contains("limgrave") || n.Contains("weeping") || n.Contains("stormveil") || n.Contains("morne") ||
                n.Contains("godrick") || n.Contains("margit") || n.Contains("darriwil") || n.Contains("gatefront"))
                return EntityProgressionTier.Early;

            // Endgame landmarks
            if (n.Contains("haligtree") || n.Contains("malenia") || n.Contains("maliketh") || n.Contains("mohg") ||
                n.Contains("placidusax") || n.Contains("elden beast") || n.Contains("snowfield") || n.Contains("mountaintop") ||
                n.Contains("castle sol") || n.Contains("niall") || n.Contains("farum azula"))
                return EntityProgressionTier.Endgame;

            // Late game landmarks
            if (n.Contains("altus") || n.Contains("leyndell") || n.Contains("volcano") || n.Contains("gelmir") ||
                n.Contains("rykard") || n.Contains("godfrey") || n.Contains("ordovis") || n.Contains("auriza") ||
                n.Contains("elemer") || n.Contains("shaded castle"))
                return EntityProgressionTier.Late;

            // Mid game landmarks
            if (n.Contains("liurnia") || n.Contains("raya lucaria") || n.Contains("caria") || n.Contains("rennala") ||
                n.Contains("radahn") || n.Contains("caelid") || n.Contains("redmane") || n.Contains("siofra") ||
                n.Contains("ainsel") || n.Contains("dragonbarrow"))
                return EntityProgressionTier.Mid;

            // ID boundary heuristics
            if (id >= 10000 && id < 20100) return EntityProgressionTier.Early;
            if (id >= 20100 && id < 20300) return EntityProgressionTier.Late;
            if (id >= 20300 && id < 20360) return EntityProgressionTier.Early;
            if (id >= 20360 && id < 20400) return EntityProgressionTier.Mid;
            if (id >= 20400 && id < 20470) return EntityProgressionTier.Late;
            if (id >= 20470 && id < 20600) return EntityProgressionTier.Endgame;

            return EntityProgressionTier.Early;
        }
    }
}
