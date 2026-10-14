using System.Collections.Generic;

namespace LootForge.RegTool
{
    public record CuratedWeapon(int Id, string Name, EntityProgressionTier Tier);

    public static class CuratedWeaponPool
    {
        public static readonly List<CuratedWeapon> WEAPONS = new()
        {
            // Early (Tier 1)
            new(8000000, "Bloodhound's Fang", EntityProgressionTier.Early),
            new(9000000, "Uchigatana", EntityProgressionTier.Early),
            new(3010000, "Claymore", EntityProgressionTier.Early),
            new(3020000, "Lordsworn's Greatsword", EntityProgressionTier.Early),
            new(10000000, "Twinblade", EntityProgressionTier.Early),
            new(2020000, "Reduvia", EntityProgressionTier.Early),
            new(6000000, "Great Epee", EntityProgressionTier.Early),
            new(9040000, "Nagakiba", EntityProgressionTier.Early),
            new(4100000, "Grafted Blade Greatsword", EntityProgressionTier.Early),
            new(18010000, "Golden Halberd", EntityProgressionTier.Early),
            new(13010000, "Nightrider Flail", EntityProgressionTier.Early),
            new(8010000, "Dismounter", EntityProgressionTier.Early),
            new(4010000, "Zweihander", EntityProgressionTier.Early),
            new(11020000, "Morning Star", EntityProgressionTier.Early),

            // Mid (Tier 2)
            new(9060000, "Moonveil", EntityProgressionTier.Mid),
            new(3090000, "Dark Moon Greatsword", EntityProgressionTier.Mid),
            new(4070000, "Starscourge Greatsword", EntityProgressionTier.Mid),
            new(4060000, "Godslayer's Greatsword", EntityProgressionTier.Mid),
            new(2070000, "Carian Knight's Sword", EntityProgressionTier.Mid),
            new(20010000, "Winged Scythe", EntityProgressionTier.Mid),
            new(2080000, "Sword of Night and Flame", EntityProgressionTier.Mid),
            new(16040000, "Cross-Naginata", EntityProgressionTier.Mid),
            new(4000000, "Greatsword (Guts)", EntityProgressionTier.Mid),
            new(8040000, "Magma Wyrm's Scalesword", EntityProgressionTier.Mid),
            new(4080000, "Ruins Greatsword", EntityProgressionTier.Mid),
            new(12210000, "Rotten Battle Hammer", EntityProgressionTier.Mid),
            new(18060000, "Guardian's Swordspear", EntityProgressionTier.Mid),
            new(10040000, "Eleonora's Poleblade", EntityProgressionTier.Mid),

            // Late (Tier 3)
            new(3140000, "Blasphemous Blade", EntityProgressionTier.Late),
            new(9080000, "Rivers of Blood", EntityProgressionTier.Late),
            new(3150000, "Marais Executioner's Sword", EntityProgressionTier.Late),
            new(8070000, "Morgott's Cursed Sword", EntityProgressionTier.Late),
            new(16140000, "Bolt of Gransax", EntityProgressionTier.Late),
            new(3060000, "Ordovis's Greatsword", EntityProgressionTier.Late),
            new(10020000, "Godskin Peeler", EntityProgressionTier.Late),
            new(6010000, "Godskin Stitcher", EntityProgressionTier.Late),
            new(16130000, "Inquisitor's Girandole", EntityProgressionTier.Late),
            new(23000000, "Prelate's Inferno Crozier", EntityProgressionTier.Late),
            new(17020000, "Siluria's Tree", EntityProgressionTier.Late),
            new(17010000, "Vyke's War Spear", EntityProgressionTier.Late),
            new(3120000, "Death's Poker", EntityProgressionTier.Late),

            // Endgame (Tier 4)
            new(9070000, "Hand of Malenia", EntityProgressionTier.Endgame),
            new(4090000, "Maliketh's Black Blade", EntityProgressionTier.Endgame),
            new(3160000, "Sacred Relic Sword", EntityProgressionTier.Endgame),
            new(17040000, "Mohgwyn's Sacred Spear", EntityProgressionTier.Endgame),
            new(23050000, "Giant-Crusher", EntityProgressionTier.Endgame),
            new(7030000, "Dragon King's Cragblade", EntityProgressionTier.Endgame),
            new(3170000, "Golden Order Greatsword", EntityProgressionTier.Endgame),
            new(8050000, "Zamor Curved Sword", EntityProgressionTier.Endgame),
            new(21120000, "Veteran's Prosthesis", EntityProgressionTier.Endgame),
            new(4050000, "Fallingstar Beast Jaw", EntityProgressionTier.Endgame),
            new(7040000, "Eclipse Shotel", EntityProgressionTier.Endgame),
            new(4040000, "Royal Greatsword", EntityProgressionTier.Endgame)
        };
    }
}
