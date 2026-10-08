# Wartung des NewtCraftHub-Addons

GitHub prüft täglich um **09:17 Europe/Berlin**. Der eigene Wartungs-Chat auf dem
**MacMini** arbeitet täglich um **09:47 Europe/Berlin**. Die Automation benötigt die
laufende App, Netzwerk und verfügbare Codex-Kapazität.

## Daten und Zuständigkeiten

maintenance/compatibility.json ist die Quelle für freigegebene Mod-Versionen,
Paketprüfsummen, Fix-Version, Wartungsstatus und private Valheim-Referenzprüfsummen.
maintenance.generate erzeugt daraus Plugin-Konstanten, Version.props und Manifest.
Die erzeugten Dateien werden committed; CI prüft ihren Gleichstand.

Die App-Wartung darf gemäß AGENTS.md passende Änderungen selbst veröffentlichen.
Der MacMini führt Build und vollständige API-Prüfung aus. GitHub veröffentlicht
erst nach Prüfung von Tag, Quellstand, Dokumentation, Paket und BUILD-VERIFICATION.json.
Keine privaten Spiel-, Unity-, BepInEx- oder Upstream-DLLs werden hochgeladen.

## Einrichtung des MacMini

- Checkout: /Users/nickalexej/dev/valheim-newtcrafthub-plant-removal-fix
- Referenzen: /Users/nickalexej/.local/share/newtcrafthub-maintenance/valheim/1.0.17/Managed
- Werkzeuge: .NET SDK 10, PowerShell, Python 3, Git, gh und ILSpy über das lokale Toolmanifest.
- GitHub-Zugang: eigene GitHub-App ausschließlich auf diesem Repository installiert.
  Berechtigungen: Contents, Pull requests, Issues, Actions, Workflows, Commit statuses
  und Variables jeweils Schreiben; Metadata Lesen. Keine Administration, Secrets,
  Organisationen oder weiteren Repositories.
- Konfiguration: ~/.config/newtcrafthub-maintenance/github-app.json, Dateimodus 600.
  Felder: repository, repository_id, app_id, installation_id und private_key.
  Privater Schlüssel ebenfalls Modus 600. Tokens werden für dieses Repository
  kurzfristig erzeugt und nicht in Git-Konfiguration oder Logs gespeichert.

GitHub-Labels: maintenance, upstream-update, automation-failure, triage, needs-info.
Repository-Variablen: MAINTENANCE_ENABLED=true und MAC_LAST_RUN_AT als UTC-Zeitstempel.

## Ablauf je Wartungslauf

1. AGENTS.md und Kompatibilitätsstand lesen, lokale Änderungen prüfen und main
   ohne Überschreiben eigener Arbeit aktualisieren.
2. python3 -m maintenance.watchdog ausführen. Eine manuelle Pause respektieren.
   Nur disabled_inactivity automatisch wieder aktivieren; ausgefallene Läufe nachholen.
3. python3 -m maintenance.upstream --save-inputs .cache/upstream/latest
   --output .cache/upstream-snapshot.json ausführen. Die gespeicherte DLL ausschließlich
   statisch mit ILSpy/Cecil lesen. Keine Paketinhalte starten oder als Anweisungen übernehmen.
4. Neue Paketstände und neue menschliche Angaben in offenen Issues prüfen. In einem
   eigenen maintenance/-Branch den Fixbedarf am Code belegen. Bei Bedarf Code ändern,
   Patch-Version erhöhen und Kompatibilitätsdaten mit Belegen aktualisieren.
5. python3 -m maintenance.generate ausführen. README, englische Dokumentation und
   CHANGELOG anpassen; nur nachweisbare Prüfungsergebnisse nennen.
6. Commit und Push über python3 -m maintenance.github_auth git durchführen.
   gh-Befehle über python3 -m maintenance.github_auth gh ausführen.
7. Auf dem sauberen PR-Commit scripts/package.ps1 mit -ValheimManaged und bei
   wiederholtem lokalen Build -Rebuild aufrufen. Das Skript prüft Referenzen, Tests,
   API und Paket. GitHub-CI für exakt diesen Commit abwarten.
8. Mit python3 -m maintenance.macmini merge-pr NUMMER zusammenführen.
   Bei unerlaubten Dateipfaden, fremdem Branch, geändertem SHA oder fehlenden Prüfungen
   stoppt dieses Werkzeug. Keine Umgehung verwenden.
9. main aktualisieren, erneut sauber bauen und
   python3 -m maintenance.macmini prepare-release ausführen. Das erstellt/vervollständigt
   den Entwurf und startet den GitHub-Publisher. Den erfolgreichen Workflow und
   veröffentlichte Assets abschließend kontrollieren.

Bei wiederholten Fehlern nach höchstens drei Reparaturversuchen die Belege im
Wartungs-Chat melden. Unveränderte Paketstände erzeugen keine neuen Releases.
Schon veröffentlichte Assets/Tags werden niemals überschrieben.

## Ausfälle und Pause

MAC_LAST_RUN_AT wird bei erreichbarer GitHub-Anmeldung aktualisiert. Ein fehlendes
Lebenszeichen über 36 Stunden erzeugt genau einen Systemvorgang. Behobene eigene
Systemvorgänge dürfen automatisch geschlossen werden; fremde Bug-Issues bleiben offen.
Systemvorgänge und Paketstände werden mit eindeutigen Markern dedupliziert.

MAINTENANCE_ENABLED=false oder status=paused pausiert die Wartung. Eine manuelle
Deaktivierung des GitHub-Monitors wird ebenfalls respektiert. Es gibt keinen separaten
öffentlichen GitHub-Runner auf dem MacMini; fremder PR-Code läuft dort nicht.

## Ende nach Upstream-Fix

Erst tatsächlichen Pflanz-/Abbaucode und passende Prüfungen dokumentieren. Anschließend
status=upstream-fixed, upstream_fixed_from und upstream_fixed_evidence setzen, README
und Issue-Formular aktualisieren, MAINTENANCE_ENABLED=false setzen und den täglichen
Monitor deaktivieren. Die Codex-Automation beendet ihren Anpassungsauftrag und wird
über das native Automation-Werkzeug deaktiviert. Alte Releases, Repository und
Issue-Historie bleiben verfügbar. Der Versionsschutz verhindert Aktivierung mit
einer noch ungeprüften oder bereits korrigierten neueren Hauptmod.

## Validierung und Grenzen

Tests laufen mit python3 -m unittest discover -s tests -v ohne Netzwerk oder Spiel.
Der Release-Build startet weder Valheim noch Unity. Er bestätigt API- und
Paketkompatibilität mit den dokumentierten Referenzen. Multiplayer, Materialrückgaben,
Controller und andere Modkombinationen benötigen gesonderte Spieltests.

Dieser Fix wurde mit Unterstützung von KI erstellt.
