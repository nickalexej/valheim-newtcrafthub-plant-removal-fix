// Generated from maintenance/compatibility.json. Do not edit.
namespace NewtCraftHubPlantRemovalFix {
    internal static class Compatibility {
        internal const string FixVersion = "0.1.1";
        internal const string MinimumNewtVersion = "1.7.0";
        internal const string ReferenceGameVersion = "1.0.17";
        internal static readonly string[] SupportedVersions = new[] { "1.7.0" };
        internal static bool Supports(System.Version version) {
            foreach (string supported in SupportedVersions)
                if (version == new System.Version(supported)) return true;
            return false;
        }
    }
}
