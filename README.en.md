# Valheim NewtCraftHub Plant Removal Fix

Community addon for [NewtCraftHub by Anatta Labs on Thunderstore](https://thunderstore.io/c/valheim/p/Anatta_Labs/NewtCraftHub/), specifically **NewtCraftHub 1.7.0**. Fix version: **0.1.1**.

This addon enables removal of player-planted NewtCraftHub mushrooms and other pickables with the hammer or cultivator. **It requires NewtCraftHub and does not work as a standalone mod.** The runtime version check disables it when NewtCraftHub is not exactly 1.7.0, when PlantEverything is installed, or when the expected game methods are unavailable.

[German documentation](README.md) · [Latest release](https://github.com/nickalexej/valheim-newtcrafthub-plant-removal-fix/releases/latest) · [Report a bug](https://github.com/nickalexej/valheim-newtcrafthub-plant-removal-fix/issues/new/choose) · [Maintenance](MAINTENANCE.md)

## Installation

1. Close Valheim.
2. Install **Anatta_Labs-NewtCraftHub-1.7.0** and its required dependencies in your active mod profile.
3. Download `NewtCraftHubPlantRemovalFix.dll` from the release.
4. In r2modman / Thunderstore Mod Manager, open **Settings → Browse profile folder**.
5. Copy the DLL to `BepInEx/plugins/NewtCraftHubPlantRemovalFix/` inside that profile. Create the folder if necessary.
6. Enable NewtCraftHub's `Enabled` and `PlantPickables` settings, then use **Start modded**.

For a manual BepInEx installation, use the same path inside the Valheim installation you launch. Install this DLL alongside NewtCraftHub. The release ZIP includes a dependency manifest for local import; the new ZIP's automatic mod-manager import has not been tested.

Aim at a planted mushroom from close range and press/release the normal removal button with a hammer or cultivator equipped and the build menu closed. The default mouse binding is the **middle mouse button**.

The addon handles the ten pickable prefabs listed by NewtCraftHub 1.7.0. It does not enable removal of wild plants. Existing planted objects can be recognized if their creator ID and network state are valid. Each player who uses this fix needs it on their own client; multiplayer validation remains pending.

## Implementation

NewtCraftHub marks planted pickables as removable, but does not add the `item` layer to removal targeting or enable the cultivator's `m_canRemovePieces` flag. The verified Valheim 1.0.17 removal mask excludes `item`.

The prefix on `Player.UpdatePlacement` temporarily extends the mask only when the first raycast hit is a supported player-planted pickable. It also enables cultivator removal for that call. Hover detection and removal therefore share the same target. A Harmony finalizer restores both settings after returns or exceptions.

Valheim's original removal method performs distance, stamina, ward, removal-permission, network-ownership and resource-return checks. The addon does not implement its own object deletion or resource drops.

## Configuration and troubleshooting

Configuration file: `BepInEx/config/local.newtcraft.plantremovalfix.cfg`.

- `General → Enabled`: defaults to `true`.
- `Diagnostics → LogRemovalAttempts`: defaults to `true`; can be disabled after testing.

Check `BepInEx/LogOutput.log` for `Valheim-Version:`, `Bereit: Abbauziel`, `Deaktiviert:`, and `Abbauversuch`. An absent attempt entry may also mean the game did not reach the removal method, for example because input was not received or stamina was insufficient.

When reporting a problem, include the addon version, NewtCraftHub version, **game version**, equipped tool and relevant log lines with private server details removed. To uninstall, close Valheim and remove the addon DLL. It writes no custom world-save data; completed removals remain normal world changes.

## Building and validation

Use the .NET SDK **10**, **PowerShell 7**, **Python 3.11 or newer**, and game assemblies from your own installation. The plugin targets **.NET Framework 4.7.2**. The complete verification requires the reference hashes in [maintenance/compatibility.json](maintenance/compatibility.json). Game and framework libraries are not distributed in this repository or its release assets.

```powershell
./scripts/package.ps1 -ValheimManaged "C:\Program Files (x86)\Steam\steamapps\common\Valheim\valheim_Data\Managed" -VerifyApi
```

See [README.md](README.md#quellcode-bauen) for direct `dotnet` commands. The script always runs maintenance tests, static API verification and package checks. Output is written to `dist/0.1.1/`: the addon DLL, installation ZIP, `SHA256SUMS.txt`, and `BUILD-VERIFICATION.json`. A publishable proof must identify a committed, clean checkout.

The Release build passed without errors or warnings against Valheim **1.0.17**. Static checks resolved **85 API references**, validated game methods and checked Harmony state pairing. **28 maintenance tests** passed. A user reported successful planted-mushroom removal with the original addon on their gaming PC; that test's exact game version was not recorded. Version 0.1.1 keeps the original removal logic and adds compatibility declarations generated from the central file. No new gameplay test was performed for 0.1.1. Debug-file generation remains disabled.

Multiplayer, in-game refunds, every other plant prefab, controller input and all other mod combinations have not been independently tested. Static verification does not run the game.

## Automated maintenance

GitHub checks official Thunderstore metadata and package DLL/changelog hashes daily at **09:17 Europe/Berlin**, including changed contents under an existing version. One maintenance issue tracks each change. Unchanged upstream data does not create a new release.

A dedicated Codex maintenance chat on the MacMini runs daily at **09:47**. Compatibility requires inspection of actual upstream planting/removal code, a build against private game references, API/package verification, and successful GitHub checks for the same commit. A trusted publishing workflow validates the tag, commit, version declarations and release assets again. Upstream and game DLLs are never released.

Manual gameplay testing is not a gate for future stable releases; release notes state exactly which checks ran. Once code inspection and appropriate checks confirm that NewtCraftHub includes the correction, we document removal of this addon and stop automatic adaptation. The supported version list and generated plugin/package declarations come from [maintenance/compatibility.json](maintenance/compatibility.json); unverified versions remain disabled.

See [MAINTENANCE.md](MAINTENANCE.md) for setup, permitted actions, repository-scoped access, outage monitoring, pausing and retirement. Operation depends on power, networking, a running Codex app, valid authentication, usage limits and GitHub scheduling.

## Credits and license

NewtCraftHub is by **Newt / Anatta Labs**. This is a separate community addon that depends on their mod. The fix uses an independent implementation and the game's original removal method. Its source is available under the [MIT license](LICENSE).

This fix was created with AI assistance.
