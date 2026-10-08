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
- GitHub-Zugang: GitHub-Connector für Repository-/PR-Arbeit; lokale gh-Anmeldung für
  Wartungsskripte, Git-Transport, Repository-Variablen, Workflow-Starts und Release-Dateien.
  Anmeldung mit gh auth login --hostname github.com; erforderliche OAuth-Bereiche:
  repo und workflow. Fehlendes workflow-Recht mit gh auth refresh -h github.com -s workflow
  ergänzen. Keine eigene GitHub-App-Konfiguration und kein privater App-Schlüssel nötig.
- maintenance.github_auth übernimmt die aktive gh-Anmeldung intern ohne Token-Ausgabe
  oder eigene Speicherung. Lokal werden geerbte Token-Umgebungsvariablen ignoriert.
  Alle API-Aufrufe des Wartungsclients zielen auf dieses Repository; Git prüft origin.
  Die gh-Kontorechte selbst sind breiter als dieser Wartungsauftrag.
- In GitHub Actions wird ausschließlich der workfloweigene GITHUB_TOKEN des erwarteten
  Repositorys verwendet; eine interaktive gh-Anmeldung auf dem Runner ist nicht nötig.
- Der Connector ersetzt die Authentifizierung lokaler Python-Prozesse nicht. Merges
  erfolgen weiterhin ausschließlich über maintenance.macmini merge-pr; ein direktes
  Connector-Merge darf diese Prüfungen nicht umgehen.

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
   eigenen maintenance/-Branch den Fixbedarf am Code belegen und bei Bedarf Code
   oder Kompatibilitätsdaten mit Belegen aktualisieren.
5. python3 -m maintenance.generate ausführen und vor Versionssprung oder Paketbau
   python3 -m maintenance.release_policy aufrufen. Nur bei release_required=true
   die Plugin-Version erhöhen und erneut generieren. Reine Dokumentations-, Test-
   und Wartungsänderungen behalten die Plugin-Version und erzeugen keinen Release.
   README, englische Dokumentation und CHANGELOG nur passend zur Änderung anpassen;
   nur nachweisbare Prüfungsergebnisse nennen.
6. Commit und Push über python3 -m maintenance.github_auth git durchführen.
   Repository-/PR-Arbeit bevorzugt über den Connector erledigen. Für lokale gh-Aufrufe
   python3 -m maintenance.github_auth gh verwenden; der Wrapper setzt das Repository
   selbst (kein zusätzliches --repo/-R). gh api erwartet repos/OWNER/REPO als Präfix.
7. Wartungstests und maintenance.generate --check ausführen. Die Release-Entscheidung
   mit --ref HEAD --enforce für den sauberen PR-Commit prüfen. Nur bei erforderlichem
   Plugin-Release scripts/package.ps1 mit -ValheimManaged und bei wiederholtem lokalen
   Build -Rebuild aufrufen. Das Skript prüft Referenzen, Tests, API und Paket.
   GitHub-CI ist in allen Fällen für exakt diesen Commit erforderlich.
8. Mit python3 -m maintenance.macmini merge-pr NUMMER zusammenführen.
   Bei unerlaubten Dateipfaden, fremdem Branch, geändertem SHA oder fehlenden Prüfungen
   stoppt dieses Werkzeug. Keine Umgehung verwenden.
9. main aktualisieren und die Release-Entscheidung erneut prüfen. Nur bei erforderlichem
   Plugin-Release den Merge-Commit sauber bauen und python3 -m maintenance.macmini
   prepare-release ausführen. Das erstellt/vervollständigt den Entwurf und startet
   den GitHub-Publisher. Workflow-Ergebnis und veröffentlichte Assets kontrollieren.
   Ohne Plugin-Änderung endet der Lauf ohne Paketbau, Tag oder Veröffentlichung.

Bei wiederholten Fehlern nach höchstens drei Reparaturversuchen die Belege im
Wartungs-Chat melden. Unveränderte Paketstände erzeugen keine neuen Releases.
Schon veröffentlichte Assets/Tags werden niemals überschrieben.

## Entscheidung über Plugin-Releases

maintenance.release_policy liefert JSON mit baseline (Tag und Commit), release_required,
reasons, version_valid, status und owner_review_required. Ohne --ref werden auch lokale
Änderungen und neue Quelldateien gelesen; --ref HEAD prüft den committed Stand.
--enforce weist fehlende sowie sachlich unbegründete Versionssprünge zurück.

Die Basis ist die höchste veröffentlichte stabile Plugin-Version aus der GitHub-API.
Entwurf und Vorabversion zählen nicht. Der lokale Tag muss mit dem veröffentlichten
Tag übereinstimmen und ein Vorfahr des Ziel-Commits sein. Fehlende Historie/Tags werden
über den vorgesehenen Wartungszugang nachgeladen; widersprüchliche Tags niemals überschreiben.
Bei fehlender oder uneindeutiger Basis stoppt die Prüfung ohne Veröffentlichung.

Verglichen werden Plugin-Quellen einschließlich Projekt und Lockdateien, zentrale
Build-Eingaben, generierte Deklarationen ohne eigene Plugin-Versionsnummer sowie
Version und Prüfsummen der privaten Referenzbasis. Beschreibende Belege, Wartungsstatus
und reine Dokumentationsänderungen lösen keinen Release aus. Neue freigegebene
NewtCraftHub-Versionen ändern die eingebauten Deklarationen und benötigen einen Release.
Build-Konfiguration, Abhängigkeiten und Referenzbasis bleiben gesondert prüfpflichtig.

Merge-Werkzeug, Release-Vorbereitung und Publisher verwenden dieselbe Entscheidung.
Bereits veröffentlichte Versionen benötigen bei unveränderten Plugin-Eingaben keine
neuen lokalen Artefakte. Ein absichtlich angeforderter lokaler Prüfbuild bleibt über
scripts/package.ps1 möglich. Normale Pushes starten weiterhin keine Veröffentlichung.
Änderungen am Wartungsablauf selbst werden als PR vorgelegt und nicht automatisch gemergt.

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
