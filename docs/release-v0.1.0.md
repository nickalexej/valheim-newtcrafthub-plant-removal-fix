# Plant Removal Fix 0.1.0 für NewtCraftHub 1.7.0

Community-Addon für [NewtCraftHub von Anatta Labs](https://thunderstore.io/c/valheim/p/Anatta_Labs/NewtCraftHub/). Dieser Release benötigt **NewtCraftHub exakt in Version 1.7.0** und funktioniert nicht eigenständig.

## Korrektur

Ergänzt die Zielerkennung für gepflanzte Pilze und andere NewtCraftHub-Sammelpflanzen sowie die Abbau-Freigabe des Kultivators. Valheims normale Abbaumethode bleibt für Zugriffsprüfungen, Netzwerkbesitz und Ressourcenrückgabe zuständig.

## Installation

1. Valheim schließen.
2. **Anatta_Labs-NewtCraftHub-1.7.0** und dessen Abhängigkeiten im aktiven Mod-Profil installieren.
3. `NewtCraftHubPlantRemovalFix.dll` aus diesem Release herunterladen.
4. Über **Settings → Browse profile folder** den Profilordner öffnen.
5. Die DLL nach `BepInEx/plugins/NewtCraftHubPlantRemovalFix/` kopieren.
6. NewtCraftHub mit `Enabled = true` und `PlantPickables = true` aktivieren und das Spiel modifiziert starten.

Ein gepflanzter Pilz kann danach mit der normalen Abbautaste des Hammers oder Kultivators entfernt werden; Standardbelegung: mittlere Maustaste drücken und loslassen.

## Assets

- **NewtCraftHubPlantRemovalFix.dll**: direkt installierbare Plugin-DLL.
- **NewtCraftHubPlantRemovalFix-0.1.0-for-NewtCraftHub-1.7.0.zip**: Installationspaket mit DLL, Anleitung, Icon und Manifest. Die Abhängigkeit `Anatta_Labs-NewtCraftHub-1.7.0` steht ausdrücklich im Manifest. Ein automatischer Import des neuen Pakets im Mod Manager wurde noch nicht getestet.
- **SHA256SUMS.txt**: Prüfsummen der beiden Dateien.

GitHub bietet den Quellcode des Release-Tags zusätzlich als ZIP und TAR.GZ an.

## Prüfung und Versionsgrenzen

Release-Build gegen Valheim **1.0.17** ohne Fehler oder Warnungen; **83 API-Verweise** statisch geprüft. Ein Benutzer hat erfolgreichen Pilz-Abbau mit demselben Plugin-Quellcode auf seinem Gaming-PC bestätigt. Die genaue Valheim-Version dieses Spieltests wurde nicht festgehalten. Mehrspielerbetrieb und alle weiteren Mod-Kombinationen wurden nicht gesondert geprüft.

Bei anderen NewtCraftHub-Versionen als **1.7.0**, installiertem PlantEverything oder unpassenden Spielmethoden deaktiviert sich der Fix.

Dieser Fix wurde mit Unterstützung von KI erstellt.
