using System;
using System.IO;
using System.Linq;
using SoulsFormats;
using SoulsFormats.Cryptography;

namespace LootForge.RegTool
{
    public static class TutorialFinder
    {
        public static void Find()
        {
            string regPath = @"C:\Users\bigra\AppData\Local\garyttierney\me3\config\profiles\eldenring-mods\Ordo Perfectus\Ordo Perfectus\regulation.bin";
            string defsDir = @"tools\vendor\Paramdex\ER\Defs";
            var bnd = RegulationDecryptor.DecryptERRegulation(regPath);
            var npcF = bnd.Files.First(f => f.Name.EndsWith("NpcParam.param"));
            var npcParam = PARAM.Read(npcF.Bytes);
            string xmlFile = Path.Combine(defsDir, "NpcParam.xml");
            if (File.Exists(xmlFile))
            {
                var def = PARAMDEF.XmlDeserialize(xmlFile, false, false);
                npcParam.ApplyParamdefSomewhatCarefully(def);
            }

            Console.WriteLine("=== NPCs with map 18 or 'Tutorial' / 'Godrick' ===");
            foreach (var r in npcParam.Rows)
            {
                string name = r.Name ?? "";
                if (r.ID >= 18000000 && r.ID < 19000000)
                {
                    int elot = ParamHelper.GetCellInt(r, "itemLotId_enemy");
                    int mlot = ParamHelper.GetCellInt(r, "itemLotId_map");
                    Console.WriteLine($"NPC ID={r.ID} Name='{name}' enemyLot={elot} mapLot={mlot}");
                }
                else if (name.Contains("Godrick", StringComparison.OrdinalIgnoreCase) && (name.Contains("Boss") || name.Contains("Tutorial") || name.Contains("Soldier") || r.ID == 43110000 || r.ID == 431100000))
                {
                    int elot = ParamHelper.GetCellInt(r, "itemLotId_enemy");
                    int mlot = ParamHelper.GetCellInt(r, "itemLotId_map");
                    Console.WriteLine($"NPC ID={r.ID} Name='{name}' enemyLot={elot} mapLot={mlot}");
                }
            }
        }
    }
}
