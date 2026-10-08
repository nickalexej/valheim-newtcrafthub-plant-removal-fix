using System;
using System.Collections.Generic;
using System.Reflection;
using BepInEx;
using BepInEx.Bootstrap;
using BepInEx.Configuration;
using HarmonyLib;
using UnityEngine;

namespace NewtCraftHubPlantRemovalFix
{
    [BepInPlugin(PluginGuid, "NewtCraftHub Plant Removal Fix", Compatibility.FixVersion)]
    [BepInDependency(NewtGuid, Compatibility.MinimumNewtVersion)]
    [BepInProcess("valheim.exe")]
    [BepInProcess("valheim")]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "local.newtcraft.plantremovalfix";
        public const string NewtGuid = "newton.newtcraftboxes";
        internal static Plugin? Instance;

        private Harmony? _harmony;
        private ConfigEntry<bool>? _enabled;
        private ConfigEntry<bool>? _logAttempts;
        private ConfigEntry<bool>? _newtEnabled;
        private ConfigEntry<bool>? _plantPickables;
        internal int ItemMask { get; private set; }
        private bool _ready;

        private void Awake()
        {
            Instance = this;
            _enabled = Config.Bind("General", "Enabled", true,
                "Ergaenzt den Abbau gepflanzter NewtCraftHub-Sammelpflanzen.");
            _logAttempts = Config.Bind("Diagnostics", "LogRemovalAttempts", true,
                "Schreibt erkannte Abbauversuche und deren Ergebnis in BepInEx/LogOutput.log.");
            LogGameVersion();

            if (!Chainloader.PluginInfos.TryGetValue(NewtGuid, out var newt) ||
                !Compatibility.Supports(newt.Metadata.Version))
            {
                Logger.LogWarning("Deaktiviert: NewtCraftHub-Version nicht freigegeben. Unterstuetzt: " +
                    string.Join(", ", Compatibility.SupportedVersions));
                return;
            }
            if (Chainloader.PluginInfos.ContainsKey("advize.PlantEverything"))
            {
                Logger.LogWarning("Deaktiviert: PlantEverything ist installiert und uebernimmt die Sammelpflanzen.");
                return;
            }
            if (!newt.Instance.Config.TryGetEntry("1 - General", "Enabled", out _newtEnabled) ||
                !newt.Instance.Config.TryGetEntry("0 - Features", "PlantPickables", out _plantPickables))
            {
                Logger.LogWarning("Deaktiviert: NewtCraftHub-Konfiguration wurde nicht erkannt.");
                return;
            }

            var update = AccessTools.DeclaredMethod(typeof(Player), "UpdatePlacement",
                new[] { typeof(bool), typeof(float) });
            var remove = AccessTools.DeclaredMethod(typeof(Player), "RemovePiece", Type.EmptyTypes);
            var hover = AccessTools.DeclaredMethod(typeof(Player), "UpdateWearNTearHover", Type.EmptyTypes);
            var maskField = AccessTools.Field(typeof(Player), "m_removeRayMask");
            var itemField = AccessTools.Field(typeof(Player), "m_rightItem");
            var removeField = AccessTools.Field(typeof(PieceTable), "m_canRemovePieces");
            ItemMask = LayerMask.GetMask("item");
            if (update == null || update.ReturnType != typeof(void) ||
                remove == null || remove.ReturnType != typeof(bool) ||
                hover == null || hover.ReturnType != typeof(void) ||
                maskField?.FieldType != typeof(int) ||
                itemField?.FieldType != typeof(ItemDrop.ItemData) ||
                removeField?.FieldType != typeof(bool) ||
                ItemMask == 0)
            {
                Logger.LogWarning("Deaktiviert: Valheim-Methoden oder item-Ebene passen nicht zum Test-Fix. Bitte Log und Spielversion pruefen.");
                return;
            }

            _harmony = new Harmony(PluginGuid);
            try
            {
                // Beide Schritte muessen dieselbe Maske sehen: Hover zuerst, danach RemovePiece.
                _harmony.Patch(update,
                    prefix: new HarmonyMethod(typeof(PlacementPatch), nameof(PlacementPatch.Prefix)),
                    finalizer: new HarmonyMethod(typeof(PlacementPatch), nameof(PlacementPatch.Finalizer)));
                _harmony.Patch(remove,
                    prefix: new HarmonyMethod(typeof(RemovalDiagnostics), nameof(RemovalDiagnostics.Prefix)),
                    postfix: new HarmonyMethod(typeof(RemovalDiagnostics), nameof(RemovalDiagnostics.Postfix)));
                _ready = true;
                Logger.LogInfo("Bereit: Abbauziel fuer gepflanzte NewtCraftHub-Sammelpflanzen wird ergaenzt (Hammer/Kultivator). " +
                    "Referenzpruefung: Valheim " + Compatibility.ReferenceGameVersion +
                    "; NewtCraftHub " + newt.Metadata.Version + ".");
            }
            catch (Exception exception)
            {
                _harmony.UnpatchSelf();
                Logger.LogError("Test-Fix konnte nicht aktiviert werden: " + exception);
            }
        }

        internal bool IsActive => _ready && _enabled?.Value == true &&
            _newtEnabled?.Value == true && _plantPickables?.Value == true;

        internal void LogAttempt(string text)
        {
            if (_logAttempts?.Value == true)
                Logger.LogInfo(text);
        }

        private void LogGameVersion()
        {
            try
            {
                var method = AccessTools.DeclaredMethod(typeof(global::Version), "GetVersionString",
                    new[] { typeof(bool) });
                var version = method?.Invoke(null, new object[] { false });
                Logger.LogInfo("Valheim-Version: " + (version ?? "nicht erkannt"));
            }
            catch (Exception exception)
            {
                Logger.LogDebug("Spielversion konnte nicht gelesen werden: " + exception.Message);
            }
        }

        private void OnDestroy()
        {
            _ready = false;
            _harmony?.UnpatchSelf();
            if (ReferenceEquals(Instance, this))
                Instance = null;
        }
    }

    internal static class PlantTarget
    {
        // Dieselben Prefab-Namen wie die Sammelpflanzenliste in NewtCraftHub 1.7.0.
        private static readonly HashSet<string> Prefabs = new HashSet<string>(StringComparer.Ordinal)
        {
            "RaspberryBush", "BlueberryBush", "CloudberryBush",
            "Pickable_Mushroom", "Pickable_Mushroom_yellow", "Pickable_Mushroom_blue",
            "Pickable_Thistle", "Pickable_Dandelion", "Pickable_SmokePuff", "Pickable_Fiddlehead"
        };

        internal static bool TryTool(Player player, ItemDrop.ItemData? item,
            out PieceTable? table, out bool cultivator)
        {
            table = null;
            cultivator = false;
            if (player != Player.m_localPlayer || !player.InPlaceMode() || player.IsDead())
                return false;
            if (item?.m_shared == null)
                return false;
            cultivator = item.m_shared.m_name == "$item_cultivator";
            if (!cultivator && item.m_shared.m_name != "$item_hammer")
                return false;
            table = item.m_shared.m_buildPieces;
            return table != null;
        }

        internal static Piece? Raycast(int mask)
        {
            if (!GameCamera.instance || !Physics.Raycast(GameCamera.instance.transform.position,
                    GameCamera.instance.transform.forward, out var hit, 50f, mask))
                return null;

            // Nur der erste Treffer zaehlt. Waende und andere Objekte werden nicht durchdrungen.
            var piece = hit.collider.GetComponentInParent<Piece>();
            if (!piece || !piece.m_canBeRemoved || !piece.IsPlacedByPlayer() ||
                !piece.GetComponent<Pickable>() || !Prefabs.Contains(Utils.GetPrefabName(piece.gameObject)))
                return null;
            var view = piece.GetComponent<ZNetView>();
            return view && view.IsValid() ? piece : null;
        }
    }

    internal static class PlacementPatch
    {
        internal sealed class State
        {
            internal int OriginalMask;
            internal PieceTable? Table;
            internal bool OriginalCanRemove;
        }

        [HarmonyPriority(Priority.Last)]
        internal static void Prefix(Player __instance, ItemDrop.ItemData? ___m_rightItem,
            ref int ___m_removeRayMask, out State? __state)
        {
            __state = null;
            var plugin = Plugin.Instance;
            if (plugin == null || !plugin.IsActive ||
                !PlantTarget.TryTool(__instance, ___m_rightItem, out var table, out var cultivator))
                return;

            int extendedMask = ___m_removeRayMask | plugin.ItemMask;
            if (!PlantTarget.Raycast(extendedMask))
                return;

            __state = new State
            {
                OriginalMask = ___m_removeRayMask,
                Table = cultivator ? table : null,
                OriginalCanRemove = table!.m_canRemovePieces
            };
            ___m_removeRayMask = extendedMask;
            if (cultivator)
                table!.m_canRemovePieces = true;
        }

        internal static void Finalizer(ref int ___m_removeRayMask, State? __state)
        {
            // Ein Harmony-Finalizer laeuft auch bei vorzeitigem Return und bei Ausnahmen.
            // Die Ausnahme des Spiels wird weder unterdrueckt noch ersetzt.
            if (__state == null)
                return;
            ___m_removeRayMask = __state.OriginalMask;
            if (__state.Table)
                __state.Table!.m_canRemovePieces = __state.OriginalCanRemove;
        }
    }

    internal static class RemovalDiagnostics
    {
        internal static void Prefix(Player __instance, ItemDrop.ItemData? ___m_rightItem,
            int ___m_removeRayMask, out string? __state)
        {
            __state = null;
            var plugin = Plugin.Instance;
            if (plugin == null || !plugin.IsActive ||
                !PlantTarget.TryTool(__instance, ___m_rightItem, out _, out _))
                return;
            var piece = PlantTarget.Raycast(___m_removeRayMask);
            if (piece)
                __state = Utils.GetPrefabName(piece!.gameObject);
        }

        internal static void Postfix(bool __result, string? __state)
        {
            if (__state != null)
                Plugin.Instance?.LogAttempt($"Abbauversuch {__state}: {(__result ? "erfolgreich" : "vom Spiel abgelehnt; Schutzgebiet, Entfernung und Werkzeug pruefen")}.");
        }
    }
}
