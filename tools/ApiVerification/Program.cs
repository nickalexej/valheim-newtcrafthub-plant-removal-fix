using Mono.Cecil;
using Mono.Cecil.Cil;

if (args.Length != 3)
    throw new ArgumentException("Aufruf: ApiVerification <Fix.dll> <Valheim-Managed> <NuGet-Pakete>");
var resolver = new DefaultAssemblyResolver();
resolver.AddSearchDirectory(args[1]);
resolver.AddSearchDirectory(Path.Combine(args[2], "bepinex.baselib/5.4.20/lib/net35"));
resolver.AddSearchDirectory(Path.Combine(args[2], "harmonyx/2.10.1/lib/net45"));
resolver.AddSearchDirectory(Path.Combine(args[2], "microsoft.netframework.referenceassemblies.net472/1.0.3/build/.NETFramework/v4.7.2"));
using var fix = AssemblyDefinition.ReadAssembly(args[0], new ReaderParameters { AssemblyResolver = resolver });
using var game = AssemblyDefinition.ReadAssembly(Path.Combine(args[1], "assembly_valheim.dll"),
    new ReaderParameters { AssemblyResolver = resolver });
var player = game.MainModule.Types.Single(type => type.FullName == "Player");
var update = player.Methods.Single(method => method.Name == "UpdatePlacement" &&
    method.Parameters.Select(p => p.ParameterType.FullName).SequenceEqual(new[] { "System.Boolean", "System.Single" }));
var remove = player.Methods.Single(method => method.Name == "RemovePiece" && method.Parameters.Count == 0);
Require(update.ReturnType.FullName == "System.Void", "UpdatePlacement-Signatur");
Require(remove.ReturnType.FullName == "System.Boolean", "RemovePiece-Signatur");
Require(player.Fields.Single(f => f.Name == "m_removeRayMask").FieldType.FullName == "System.Int32", "Zielmaske");
var humanoid = game.MainModule.Types.Single(type => type.FullName == "Humanoid");
Require(humanoid.Fields.Single(f => f.Name == "m_rightItem").FieldType.FullName == "ItemDrop/ItemData", "Werkzeugfeld");

var updateCalls = Calls(update).ToArray();
Require(Array.IndexOf(updateCalls, "Player::UpdateWearNTearHover") >= 0 &&
    Array.IndexOf(updateCalls, "Player::UpdateWearNTearHover") < Array.IndexOf(updateCalls, "Player::RemovePiece"),
    "Hover-Erkennung vor Abbau");
var removeCalls = Calls(remove).ToHashSet();
foreach (var required in new[] { "Location::IsInsideNoBuildLocation", "PrivateArea::CheckAccess",
    "Player::CheckCanRemovePiece", "Piece::CanBeRemoved", "ZNetView::ClaimOwnership", "Piece::DropResources", "ZNetScene::Destroy" })
    Require(removeCalls.Contains(required), "Original-Abbau enthaelt " + required);

var failures = new List<string>();
var checkedReferences = 0;
foreach (var member in fix.MainModule.GetMemberReferences())
{
    try
    {
        var resolved = member switch
        {
            MethodReference method => (object?)method.Resolve(),
            FieldReference field => field.Resolve(),
            _ => null
        };
        if (resolved == null)
            failures.Add(member.FullName);
        else
            checkedReferences++;
    }
    catch (Exception ex)
    {
        failures.Add(member.FullName + ": " + ex.Message);
    }
}
Require(failures.Count == 0, "Alle API-Verweise aufloesbar: " + string.Join("\n", failures));

// Bei manueller Harmony-Registrierung gehoeren Prefix und Finalizer fuer __state in dieselbe Klasse.
var placement = fix.MainModule.Types.Single(t => t.Name == "PlacementPatch");
var prefix = placement.Methods.Single(m => m.Name == "Prefix");
var finalizer = placement.Methods.Single(m => m.Name == "Finalizer");
Require(prefix.Parameters.Any(p => p.Name == "__state" && p.IsOut), "Prefix legt Aufrufzustand an");
Require(finalizer.Parameters.Single(p => p.Name == "__state").ParameterType.FullName ==
    ((ByReferenceType)prefix.Parameters.Single(p => p.Name == "__state").ParameterType).ElementType.FullName,
    "Finalizer verwendet denselben Zustands-Typ");
Require(finalizer.ReturnType.FullName == "System.Void" &&
    finalizer.Parameters.All(p => p.Name != "__exception"), "Finalizer unterdrueckt keine Spiel-Ausnahme");
Require(Calls(prefix).All(call => !call.EndsWith("::Destroy") && !call.EndsWith("::DropResources")),
    "Prefix loescht keine Objekte und erzeugt keine Ressourcen");
Require(finalizer.Body.Instructions.Any(i => i.OpCode == OpCodes.Stind_I4), "Finalizer stellt Zielmaske wieder her");
Require(finalizer.Body.Instructions.Any(i => i.Operand is FieldReference f &&
    i.OpCode == OpCodes.Stfld && f.Name == "m_canRemovePieces"), "Finalizer stellt Werkzeug-Freigabe wieder her");

Console.WriteLine($"PASS: {checkedReferences} API-Verweise aufgeloest; Spielmethoden, Original-Abbaupruefungen und Harmony-Zustandszuordnung geprueft.");
Console.WriteLine("Dies ist eine statische Pruefung. Valheim und Unity wurden nicht gestartet.");

static IEnumerable<string> Calls(MethodDefinition method) => method.Body.Instructions
    .Where(i => i.OpCode == OpCodes.Call || i.OpCode == OpCodes.Callvirt)
    .Select(i => i.Operand).OfType<MethodReference>()
    .Select(m => m.DeclaringType.FullName + "::" + m.Name);
static void Require(bool condition, string description)
{
    if (!condition)
        throw new InvalidOperationException(description);
}
