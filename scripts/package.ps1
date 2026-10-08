param(
    [Parameter(Mandatory = $true)]
    [string]$ValheimManaged,
    [switch]$VerifyApi
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$project = Join-Path $repoRoot 'src/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.csproj'
$gameReferences = (Resolve-Path -LiteralPath $ValheimManaged).Path
$manifest = Get-Content -LiteralPath (Join-Path $repoRoot 'packaging/manifest.json') -Raw | ConvertFrom-Json
$fixVersion = $manifest.version_number
$requiredMod = $manifest.dependencies[0]
$upstreamVersion = ($requiredMod -split '-')[-1]
$dist = Join-Path $repoRoot 'dist'
$staging = Join-Path $dist "staging-$fixVersion"
$dllName = 'NewtCraftHubPlantRemovalFix.dll'
$dll = Join-Path $repoRoot "src/NewtCraftHubPlantRemovalFix/bin/Release/net472/$dllName"
$zipName = "NewtCraftHubPlantRemovalFix-$fixVersion-for-NewtCraftHub-$upstreamVersion.zip"

Push-Location $repoRoot
try {
    dotnet restore $project --locked-mode
    if ($LASTEXITCODE -ne 0) { throw 'NuGet restore failed.' }
    dotnet build $project -c Release --no-restore "-p:ValheimManaged=$gameReferences"
    if ($LASTEXITCODE -ne 0) { throw 'Plugin build failed.' }

    if ($VerifyApi) {
        $nugetCache = $env:NUGET_PACKAGES
        if (-not $nugetCache) {
            $nugetCache = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.nuget/packages'
        }
        dotnet run --project (Join-Path $repoRoot 'tools/ApiVerification/ApiVerification.csproj') -c Release -- $dll $gameReferences $nugetCache
        if ($LASTEXITCODE -ne 0) { throw 'Static API verification failed.' }
    }

    $pluginDir = Join-Path $staging 'BepInEx/plugins/NewtCraftHubPlantRemovalFix'
    New-Item -ItemType Directory -Force -Path $pluginDir | Out-Null
    Copy-Item -LiteralPath $dll -Destination (Join-Path $pluginDir $dllName)
    foreach ($name in @('README.md', 'README.en.md', 'LICENSE', 'CHANGELOG.md')) {
        Copy-Item -LiteralPath (Join-Path $repoRoot $name) -Destination $staging
    }
    Copy-Item -LiteralPath (Join-Path $repoRoot 'packaging/manifest.json') -Destination $staging
    Copy-Item -LiteralPath (Join-Path $repoRoot 'packaging/icon.png') -Destination $staging
    Copy-Item -LiteralPath $dll -Destination (Join-Path $dist $dllName)

    $zip = Join-Path $dist $zipName
    if (Test-Path -LiteralPath $zip) { throw "Release package already exists: $zip. Remove it explicitly before rebuilding." }
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zip

    $checksums = foreach ($asset in @((Join-Path $dist $dllName), $zip)) {
        $hash = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $([IO.Path]::GetFileName($asset))"
    }
    $checksums | Set-Content -LiteralPath (Join-Path $dist 'SHA256SUMS.txt') -Encoding ascii
    Write-Host "Release assets created in $dist"
} finally {
    Pop-Location
}
