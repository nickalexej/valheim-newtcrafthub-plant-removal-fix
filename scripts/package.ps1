param(
    [Parameter(Mandatory = $true)][string]$ValheimManaged,
    [switch]$VerifyApi,
    [switch]$Rebuild
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    python3 -m maintenance.generate --check
    if ($LASTEXITCODE -ne 0) { throw 'Compatibility declarations are stale.' }
    python3 -m maintenance.build_proof --references $ValheimManaged
    if ($LASTEXITCODE -ne 0) { throw 'Unreviewed game references.' }
    python3 -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Maintenance regression tests failed.' }
    $manifest = Get-Content -LiteralPath 'packaging/manifest.json' -Raw | ConvertFrom-Json
    $config = Get-Content -LiteralPath 'maintenance/compatibility.json' -Raw | ConvertFrom-Json
    $version = $manifest.version_number
    $latest = @($config.supported.version | Sort-Object { [version]$_ })[-1]
    $dist = Join-Path $repoRoot "dist/$version"
    New-Item -ItemType Directory -Force -Path $dist | Out-Null
    $zip = Join-Path $dist "NewtCraftHubPlantRemovalFix-$version-for-NewtCraftHub-$latest.zip"
    if ((Test-Path -LiteralPath $zip) -and !$Rebuild) { throw 'Local package exists; use -Rebuild for a new local build.' }
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip }
    $project = 'src/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.csproj'
    dotnet restore $project --locked-mode
    if ($LASTEXITCODE -ne 0) { throw 'Restore failed.' }
    dotnet build $project -c Release --no-restore "-p:ValheimManaged=$ValheimManaged"
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    $dll = Join-Path $repoRoot 'src/NewtCraftHubPlantRemovalFix/bin/Release/net472/NewtCraftHubPlantRemovalFix.dll'
    $nugetCache = $env:NUGET_PACKAGES
    if (!$nugetCache) { $nugetCache = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.nuget/packages' }
    dotnet run --project 'tools/ApiVerification/ApiVerification.csproj' -c Release -- $dll $ValheimManaged $nugetCache (Join-Path $dist 'api-check.json')
    if ($LASTEXITCODE -ne 0) { throw 'Static API verification failed.' }
    $staging = Join-Path $dist ("staging-" + [Guid]::NewGuid().ToString('N'))
    $plugin = Join-Path $staging 'BepInEx/plugins/NewtCraftHubPlantRemovalFix'
    New-Item -ItemType Directory -Force -Path $plugin | Out-Null
    Copy-Item -LiteralPath $dll -Destination (Join-Path $plugin 'NewtCraftHubPlantRemovalFix.dll')
    foreach ($name in @('README.md','README.en.md','LICENSE','CHANGELOG.md')) {
        Copy-Item -LiteralPath (Join-Path $repoRoot $name) -Destination $staging
    }
    foreach ($name in @('manifest.json','icon.png')) {
        Copy-Item -LiteralPath (Join-Path $repoRoot "packaging/$name") -Destination $staging
    }
    Copy-Item -LiteralPath $dll -Destination (Join-Path $dist 'NewtCraftHubPlantRemovalFix.dll')
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zip
    Remove-Item -LiteralPath $staging -Recurse
    python3 -m maintenance.build_proof --references $ValheimManaged --proof
    if ($LASTEXITCODE -ne 0) { throw 'Build proof failed.' }
    python3 scripts/verify_package.py
    if ($LASTEXITCODE -ne 0) { throw 'Package verification failed.' }
    Write-Host "PASS: verified release assets in $dist"
} finally { Pop-Location }
