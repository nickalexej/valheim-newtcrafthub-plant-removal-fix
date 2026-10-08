# Valheim NewtCraftHub Plant Removal Fix

**Community-Addon für [NewtCraftHub von Anatta Labs auf Thunderstore](https://thunderstore.io/c/valheim/p/Anatta_Labs/NewtCraftHub/), ausschließlich für Version 1.7.0.**

Der Fix ermöglicht das Entfernen gepflanzter Pilze und anderer NewtCraftHub-Sammelpflanzen mit Bauhammer oder Kultivator. Er benötigt NewtCraftHub als Abhängigkeit und funktioniert nicht eigenständig.

[English documentation](README.en.md) · [Aktuelles Release](https://github.com/nickalexej/valheim-newtcrafthub-plant-removal-fix/releases/latest) · [Fehler melden](https://github.com/nickalexej/valheim-newtcrafthub-plant-removal-fix/issues/new/choose) · [Wartung](MAINTENANCE.md)

## Versionen und Abhängigkeiten

| Bestandteil | Version / Voraussetzung |
| --- | --- |
| Dieser Fix | **0.1.1** |
| Erforderliche Hauptmod | **Anatta_Labs-NewtCraftHub-1.7.0** |
| BepInEx | BepInExPack Valheim, entsprechend der NewtCraftHub-Installation |
| Valheim-Referenz für Build und statische Prüfung | **1.0.17** |
| NewtCraftHub-Einstellungen | `Enabled = true` und `PlantPickables = true` |

**1.7.0 bezeichnet die Version von NewtCraftHub, nicht die Version von Valheim oder des Fixes.**

Die Abhängigkeit ist im BepInEx-Plugin deklariert. Die zentrale [Kompatibilitätsdatei](maintenance/compatibility.json) führt die geprüften Versionen und DLL-Prüfsummen. Daraus werden die Versionsfreigaben im Plugin und die Paketangaben erzeugt. Dieser Release aktiviert sich ausschließlich mit NewtCraftHub **1.7.0**. Ungeprüfte Versionen bleiben deaktiviert.

Wenn `PlantEverything` installiert ist, deaktiviert sich der Fix ebenfalls, da diese Mod die Sammelpflanzen übernimmt.

## Download und Installation

Die DLL und das Installations-ZIP stehen unter [Releases](https://github.com/nickalexej/valheim-newtcrafthub-plant-removal-fix/releases).

### Mit r2modman oder Thunderstore Mod Manager

1. Valheim vollständig schließen.
2. Das verwendete Valheim-Profil öffnen und prüfen, dass **NewtCraftHub 1.7.0** und dessen Abhängigkeiten installiert sind.
3. `NewtCraftHubPlantRemovalFix.dll` aus dem Release herunterladen.
4. Über **Settings → Browse profile folder** den Profilordner öffnen.
5. Die DLL nach `BepInEx/plugins/NewtCraftHubPlantRemovalFix/` kopieren. Den Unterordner bei Bedarf anlegen.
6. Das Spiel über **Start modded** mit diesem Profil starten.

Das Installations-ZIP enthält zusätzlich ein Thunderstore-Manifest mit `Anatta_Labs-NewtCraftHub-1.7.0` als Abhängigkeit. Es ist für einen lokalen Import vorbereitet. Die manuelle Installation der DLL ist der hier dokumentierte und bereits vom Benutzer erfolgreich getestete Weg. Ein automatischer Import des neuen ZIPs wurde noch nicht im Mod Manager getestet.

### Manuelle BepInEx-Installation

1. Valheim schließen und NewtCraftHub **1.7.0** samt Abhängigkeiten installieren.
2. Die DLL in den Plugin-Ordner der Installation kopieren, aus der du das modifizierte Spiel startest:

```text
Valheim/
└── BepInEx/
    └── plugins/
        └── NewtCraftHubPlantRemovalFix/
            └── NewtCraftHubPlantRemovalFix.dll
```

3. `Enabled` und `PlantPickables` in NewtCraftHub aktivieren und das modifizierte Spiel starten.

Die DLL wird **zusätzlich** zu NewtCraftHub installiert. Du benötigst keine Dateien aus dem Quellcode-Ordner zum Spielen. Die Release-Pakete enthalten keine Spiel-, Unity-, BepInEx- oder Harmony-Bibliotheken.

## Benutzung

Einen mit NewtCraftHub gepflanzten Pilz aus kurzer Entfernung anvisieren, Hammer oder Kultivator ausrüsten und bei geschlossenem Baumenü die normale Abbautaste drücken und loslassen. Mit der Standardbelegung ist das die **mittlere Maustaste**.

Unterstützt werden die zehn Sammelpflanzen aus NewtCraftHub 1.7.0:

- Himbeer-, Blaubeer- und Moltebeersträucher.
- Rote, gelbe und blaue Pilze.
- Disteln, Löwenzahn, Rauchpilze und Fiddlehead.

Auch bereits gepflanzte Pflanzen können erkannt werden, sofern sie eine Ersteller-ID und einen gültigen Netzwerkzustand haben. Natürlich gewachsene Pflanzen werden vom Fix nicht freigegeben.

Valheim führt den Abbau aus und prüft dabei weiterhin Entfernung, Ausdauer, Schutzgebiete, Abbauverbote, Netzwerkbesitz und Materialrückgabe. Eine Beschränkung auf den ursprünglichen Pflanzer ergänzt der Fix nicht.

Der Spieler, der den Fix verwenden möchte, installiert ihn auf seinem eigenen Client. Eine zusätzliche Serverinstallation dieses Fixes ist für diesen Ablauf nicht vorgesehen. Der Mehrspielerbetrieb wurde nicht gesondert getestet.

## Was wird korrigiert?

NewtCraftHub 1.7.0 markiert seine Sammelpflanzen zwar als entfernbar, ergänzt aber nicht die Zielerkennung für die Ebene `item` und die Abbau-Freigabe des Kultivators. In der geprüften Valheim-Version 1.0.17 berücksichtigt die normale Abbau-Zielmaske diese Ebene nicht.

Der Fix erweitert die Maske vor `Player.UpdatePlacement` nur dann vorübergehend, wenn der erste Treffer eine unterstützte, von Spielern gepflanzte Sammelpflanze ist. Beim Kultivator aktiviert er für diesen Aufruf außerdem `m_canRemovePieces`.

Damit sehen Hover-Erkennung und anschließender Abbau dasselbe Ziel. Ein Harmony-Finalizer stellt die ursprünglichen Werte auch bei vorzeitigem Return oder einer Ausnahme wieder her. Der Fix verwendet die vorhandene Abbaumethode des Spiels und erzeugt keine eigenen Ressourcen oder Löschbefehle.

## Konfiguration und Diagnose

Konfigurationsdatei: `BepInEx/config/local.newtcraft.plantremovalfix.cfg`

| Abschnitt | Einstellung | Standard | Zweck |
| --- | --- | --- | --- |
| General | Enabled | `true` | Schaltet den Fix ein oder aus. |
| Diagnostics | LogRemovalAttempts | `true` | Protokolliert erkannte Abbauversuche. |

Nach einem erfolgreichen Test kann `LogRemovalAttempts` deaktiviert werden.

Bei Problemen in `BepInEx/LogOutput.log` nach diesen Texten suchen:

- `Valheim-Version:`: erkannte Spielversion.
- `Bereit: Abbauziel`: benötigte Methoden erkannt und Patches registriert.
- `Deaktiviert:`: unpassende NewtCraftHub-Version, PlantEverything oder nicht erkannte Methoden.
- `Test-Fix konnte nicht aktiviert werden:`: Fehler beim Registrieren der Patches.
- `Abbauversuch`: Ergebnis eines erkannten Aufrufs der normalen Abbaumethode.

Ein fehlender Abbau-Eintrag allein beweist keine fehlende Zielerkennung. Bei fehlender Ausdauer oder ausbleibender Eingabe erreicht das Spiel die Abbaumethode beispielsweise nicht.

Für einen Fehlerbericht werden Fix-Version, **NewtCraftHub-Version**, **Valheim-Version**, Werkzeug, kurze Reproduktion und relevante Logzeilen benötigt. Bitte private Serverdaten aus dem Log entfernen.

Zum Deinstallieren Valheim schließen und die Zusatz-DLL entfernen. Der Fix speichert keine eigenen Daten in der Weltdatei; bereits ausgeführter Abbau bleibt eine normale Änderung der Spielwelt.

## Quellcode bauen

Benötigt werden das **.NET SDK 10**, **PowerShell 7**, **Python 3.11 oder neuer** und die Bibliotheken aus einer eigenen Valheim-Installation. Die Spielebibliotheken werden nicht mitgeliefert. Der vollständige Prüfablauf verlangt die in der Kompatibilitätsdatei dokumentierten Prüfsummen; abweichende Spielreferenzen müssen zuerst geprüft und dort erfasst werden.

Aus dem Repository-Ordner zum Beispiel unter Windows ausführen und den Pfad anpassen:

```powershell
dotnet restore src/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.csproj --locked-mode
dotnet build src/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.csproj -c Release --no-restore -p:ValheimManaged="C:\Program Files (x86)\Steam\steamapps\common\Valheim\valheim_Data\Managed"
```

Die DLL entsteht unter `src/NewtCraftHubPlantRemovalFix/bin/Release/net472/`. Sie verwendet **.NET Framework 4.7.2**; das SDK 10 ist nur für die Entwicklung erforderlich.

Für Build, statische API-Prüfung und Release-Paket gibt es außerdem ein PowerShell-Skript:

```powershell
./scripts/package.ps1 -ValheimManaged "C:\Program Files (x86)\Steam\steamapps\common\Valheim\valheim_Data\Managed" -VerifyApi
```

Das Skript führt die Wartungs-Tests, die statische API-Prüfung und die Paketprüfung immer aus. Es schreibt die eigene DLL, ein Installations-ZIP, `SHA256SUMS.txt` und `BUILD-VERIFICATION.json` nach `dist/0.1.1/`. Der Prüfbericht hält Commit, private Referenz-Prüfsummen und die tatsächlich ausgeführten Prüfungen fest. Für ein veröffentlichbares Paket muss der Commit eingecheckt und der Arbeitsbaum unverändert sein.

## Automatische Wartung

GitHub prüft täglich um **09:17 Uhr, Europe/Berlin**, Thunderstore-Metadaten sowie den Changelog und die DLL im offiziellen Paket. Änderungen innerhalb derselben Mod-Version werden ebenfalls erkannt. Pro Änderung gibt es einen Wartungsvorgang; unveränderte Daten erzeugen kein weiteres Release.

Der Wartungs-Chat auf dem MacMini prüft täglich um **09:47 Uhr** neue Versionen und neue Fehlerangaben. Eine Freigabe setzt die Untersuchung des tatsächlichen Upstream-Codes, einen Build mit privaten Spielreferenzen, die API- und Paketprüfung sowie erfolgreiche GitHub-Prüfungen für denselben Commit voraus. Der Veröffentlichungs-Workflow prüft danach Tag, Quellcode-Zuordnung und alle Release-Dateien erneut. Die originale NewtCraftHub-DLL und Spielbibliotheken werden nicht veröffentlicht.

Ein manueller Spieltest ist keine Voraussetzung für künftige stabile Releases. Release-Notizen unterscheiden ausdrücklich zwischen statischer Prüfung und tatsächlich durchgeführten Spieltests. Sobald eine geprüfte NewtCraftHub-Version die Korrektur enthält, dokumentieren wir die Empfehlung zum Entfernen dieses Addons und beenden die automatische Anpassung.

Einrichtung, erlaubte automatische Aktionen, Zugangsbeschränkungen, Ausfallüberwachung und das Pausieren sind in [MAINTENANCE.md](MAINTENANCE.md) beschrieben. Ein Abschalten der Wartung wird respektiert. Betrieb und Zeitpunkt hängen von GitHub, Strom, Netzwerk, laufender Codex-App, Anmeldung und Nutzungslimits ab.

## Prüfungen und bekannte Grenzen

- Release-Build gegen die vorhandenen Valheim-1.0.17-Bibliotheken: **0 Fehler, 0 Warnungen**.
- **85 API-Verweise** der DLL statisch aufgelöst.
- Spielmethoden, Abbauprüfungen und Harmony-Zustandszuordnung geprüft.
- **27 Wartungs-Tests** für Monitor, Ausfälle, Issue-Aufnahme, Merge-Schutz und Release-Prüfung bestanden.
- Der Benutzer hat erfolgreiches Entfernen eines gepflanzten Pilzes mit dem ursprünglichen Fix auf seinem Gaming-PC bestätigt. Die genaue Valheim-Version dieses Tests wurde nicht festgehalten.
- Version 0.1.1 übernimmt die Abbaulogik des ursprünglichen Fixes und ergänzt die aus der Kompatibilitätsdatei erzeugte Versionsfreigabe. Ein neuer Spieltest für 0.1.1 wurde nicht durchgeführt. Die Build-Konfiguration lässt Debugdateien und lokale Debugpfade weg.

Nicht gesondert verifiziert sind Mehrspielerbetrieb, Materialrückgabe im Spiel, alle übrigen Sammelpflanzen, Controller-Eingabe und sämtliche Kombinationen mit anderen Mods. Die statische API-Prüfung startet weder Valheim noch Unity.

## Bezug zur Hauptmod und Lizenz

Die Hauptmod stammt von **Newt / Anatta Labs**: [NewtCraftHub auf Thunderstore](https://thunderstore.io/c/valheim/p/Anatta_Labs/NewtCraftHub/). Dieses Repository enthält ein eigenständiges Community-Addon mit einer zwingenden Abhängigkeit von dieser Hauptmod.

Der Fix verwendet eine eigene Implementierung und Valheims vorhandene Abbaumethode. Sein Quellcode steht unter der [MIT-Lizenz](LICENSE).

Dieser Fix wurde mit Unterstützung von KI erstellt.
