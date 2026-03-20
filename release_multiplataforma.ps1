param(
    [string]$Version = "",
    [string]$Repo = "",
    [string]$Branch = "",
    [switch]$BuildLocal = $true
)

$ErrorActionPreference = "Stop"

function Step($msg) {
    Write-Host $msg
}

function Ensure-Success($message) {
    if ($LASTEXITCODE -ne 0) {
        throw $message
    }
}

function Get-AppVersionFromConfig {
    param([string]$ConfigPath)
    $content = Get-Content -Path $ConfigPath -Raw -Encoding UTF8
    $m = [regex]::Match($content, 'APP_VERSION\s*=\s*"([^"]+)"')
    if (-not $m.Success) {
        throw "No se pudo leer APP_VERSION en $ConfigPath"
    }
    return $m.Groups[1].Value
}

function Set-AppVersionInConfig {
    param(
        [string]$ConfigPath,
        [string]$NewVersion
    )
    $content = Get-Content -Path $ConfigPath -Raw -Encoding UTF8
    $updated = [regex]::Replace(
        $content,
        'APP_VERSION\s*=\s*"[^"]+"',
        ('APP_VERSION = "{0}"' -f $NewVersion),
        1
    )
    if ($updated -eq $content) {
        throw "No se pudo actualizar APP_VERSION en $ConfigPath"
    }
    Set-Content -Path $ConfigPath -Value $updated -Encoding UTF8
}

function Resolve-Gh {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmdExe = Get-Command gh.exe -ErrorAction SilentlyContinue
    if ($cmdExe) { return $cmdExe.Source }
    return $null
}

Write-Host "============================================"
Write-Host "  Sistema Rampazzo - Release Multiplataforma"
Write-Host "============================================"
Write-Host ""

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$configPath = Join-Path $projectRoot "config.py"
$buildScript = Join-Path $projectRoot "build_multiplataforma.ps1"
$localBuildScript = Join-Path $projectRoot "build.py"

if (-not (Test-Path $configPath)) {
    throw "No se encontro config.py en la raiz del proyecto."
}
if (-not (Test-Path $buildScript)) {
    throw "No se encontro build_multiplataforma.ps1 en la raiz del proyecto."
}

Step "[1/8] Verificando dependencias..."
$gh = Resolve-Gh
if (-not $gh) {
    throw "No se encontro GitHub CLI (gh). Instalar desde https://cli.github.com/"
}
& $gh auth status | Out-Null
Ensure-Success "gh no esta autenticado. Ejecutar: gh auth login"
Write-Host "      OK"
Write-Host ""

Step "[2/8] Resolviendo repo y rama..."
if ([string]::IsNullOrWhiteSpace($Repo)) {
    $repoJson = & $gh repo view --json nameWithOwner | ConvertFrom-Json
    $Repo = $repoJson.nameWithOwner
}
if ([string]::IsNullOrWhiteSpace($Branch)) {
    $Branch = (& git rev-parse --abbrev-ref HEAD).Trim()
}
if ([string]::IsNullOrWhiteSpace($Repo) -or [string]::IsNullOrWhiteSpace($Branch)) {
    throw "No se pudo detectar repo/rama. Pasar -Repo y -Branch manualmente."
}
Write-Host "      Repo: $Repo"
Write-Host "      Rama: $Branch"
Write-Host ""

Step "[3/8] Verificando version..."
$currentVersion = Get-AppVersionFromConfig -ConfigPath $configPath
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $currentVersion
}
if (-not ($Version -match '^\d+\.\d+\.\d+$')) {
    throw "Version invalida '$Version'. Usar formato semver: X.Y.Z"
}
Write-Host "      Version actual en config.py: $currentVersion"
Write-Host "      Version objetivo: $Version"
Write-Host ""

Step "[4/8] Actualizando config.py..."
if ($currentVersion -ne $Version) {
    Set-AppVersionInConfig -ConfigPath $configPath -NewVersion $Version
    Write-Host "      APP_VERSION actualizada a $Version"
} else {
    Write-Host "      APP_VERSION ya estaba en $Version"
}
Write-Host ""

Step "[5/8] Commit + push de version..."
& git add -- "config.py"
Ensure-Success "No se pudo hacer git add config.py"

$staged = (& git diff --cached --name-only).Trim()
if ($staged -match 'config.py') {
    $commitMsg = "v$Version - release multiplataforma"
    & git commit -m $commitMsg -- "config.py"
    Ensure-Success "No se pudo crear commit de version."
    Write-Host "      Commit creado."
} else {
    Write-Host "      Sin cambios para commitear en config.py."
}

& git push origin HEAD
Ensure-Success "No se pudo pushear la rama al remoto."
Write-Host "      Push OK."
Write-Host ""

if ($BuildLocal) {
    Step "[6/8] Build local (Windows)..."
    & python $localBuildScript
    Ensure-Success "Fallo build local con build.py"
    Write-Host ""
} else {
    Step "[6/8] Build local (Windows)..."
    Write-Host "      Omitido por parametro -BuildLocal:`$false"
    Write-Host ""
}

Step "[7/8] Build multiplataforma..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $buildScript -Version $Version -Repo $Repo -Branch $Branch
Ensure-Success "Fallo build_multiplataforma.ps1"
Write-Host ""

Step "[8/8] Release finalizada."
Write-Host "      Version: $Version"
Write-Host "      Carpeta win:   dist_out/win-$Version"
Write-Host "      Carpeta linux: dist_out/linux-$Version"
Write-Host "      Carpeta mac:   dist_out/mac-$Version"
Write-Host ""
Write-Host "Listo."
