param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$Repo = "",
    [string]$Branch = ""
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

function Resolve-Gh {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $cmdExe = Get-Command gh.exe -ErrorAction SilentlyContinue
    if ($cmdExe) { return $cmdExe.Source }

    $candidates = @(
        "$env:ProgramFiles\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe",
        "$env:ProgramW6432\GitHub CLI\gh.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) {
            return $p
        }
    }
    return $null
}

Write-Host "============================================"
Write-Host "  Sistema Rampazzo - Build Multiplataforma"
Write-Host "  (orquestado con GitHub Actions)"
Write-Host "============================================"
Write-Host ""

Step "[1/8] Verificando GitHub CLI..."
$gh = Resolve-Gh
if (-not $gh) {
    throw "No se encontro GitHub CLI (gh). Instalar desde https://cli.github.com/ o agregarlo al PATH."
}
& $gh auth status | Out-Null
Ensure-Success "gh no esta autenticado. Ejecutar: gh auth login"
Write-Host "      OK"
Write-Host ""

Step "[2/8] Resolviendo repo y rama..."
if ([string]::IsNullOrWhiteSpace($Repo)) {
    try {
        $repoJson = & $gh repo view --json nameWithOwner | ConvertFrom-Json
        $Repo = $repoJson.nameWithOwner
    } catch {}
}
if ([string]::IsNullOrWhiteSpace($Repo)) {
    throw "No se pudo detectar el repositorio. Pasarlo como parametro o ingresarlo cuando se pida: owner/repo"
}
if ([string]::IsNullOrWhiteSpace($Branch)) {
    try {
        $branchJson = & $gh repo view $Repo --json defaultBranchRef | ConvertFrom-Json
        $Branch = $branchJson.defaultBranchRef.name
    } catch {
        $Branch = "main"
    }
}
Write-Host "      Repo: $Repo"
Write-Host "      Rama: $Branch"
Write-Host ""

$distOut = Join-Path $PSScriptRoot "dist_out"
$winDir = Join-Path $distOut ("win-" + $Version)
$linuxDir = Join-Path $distOut ("linux-" + $Version)
$macDir = Join-Path $distOut ("mac-" + $Version)
$tmpDir = Join-Path $distOut ("_tmp_download_" + $Version)
$workflow = "build.yml"

Step "[3/8] Preparando carpetas de salida..."
New-Item -ItemType Directory -Force -Path $distOut | Out-Null
if (Test-Path $winDir) { Remove-Item -Recurse -Force $winDir }
if (Test-Path $linuxDir) { Remove-Item -Recurse -Force $linuxDir }
if (Test-Path $macDir) { Remove-Item -Recurse -Force $macDir }
if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
New-Item -ItemType Directory -Force -Path $winDir, $linuxDir, $macDir, $tmpDir | Out-Null
Write-Host "      OK"
Write-Host ""

Step "[4/8] Disparando workflow $workflow..."
& $gh workflow run $workflow -R $Repo --ref $Branch
Ensure-Success "No se pudo disparar el workflow. Verificar permisos y nombre del workflow."
Write-Host "      Workflow disparado."
Write-Host ""

Step "[5/8] Obteniendo run_id..."
$runs = & $gh run list -R $Repo --workflow $workflow --branch $Branch --event workflow_dispatch --limit 1 --json databaseId | ConvertFrom-Json
if (-not $runs -or $runs.Count -eq 0) {
    throw "No se pudo obtener run_id del workflow."
}
$runId = [string]$runs[0].databaseId
Write-Host "      Run ID: $runId"
Write-Host ""

Step "[6/8] Esperando finalizacion..."
& $gh run watch $runId -R $Repo --exit-status
Ensure-Success "El workflow termino con error. Revisar GitHub Actions."
Write-Host "      Workflow completado correctamente."
Write-Host ""

Step "[7/8] Descargando artifacts..."
& $gh run download $runId -R $Repo -D $tmpDir
Ensure-Success "No se pudieron descargar artifacts."
Write-Host "      Artifacts descargados en $tmpDir"
Write-Host ""

Step "[8/8] Organizando artifacts..."
$winZip = Join-Path $tmpDir "SistemaRampazzo-Windows\SistemaRampazzo.zip"
$linuxZip = Join-Path $tmpDir "SistemaRampazzo-Linux\SistemaRampazzo.zip"
$macZip = Join-Path $tmpDir "SistemaRampazzo-macOS\SistemaRampazzo.zip"

if (Test-Path $winZip) {
    Copy-Item -Force $winZip (Join-Path $winDir ("SistemaRampazzo-win-" + $Version + ".zip"))
} else {
    Write-Warning "No se encontro artifact de Windows."
}
if (Test-Path $linuxZip) {
    Copy-Item -Force $linuxZip (Join-Path $linuxDir ("SistemaRampazzo-linux-" + $Version + ".zip"))
} else {
    Write-Warning "No se encontro artifact de Linux."
}
if (Test-Path $macZip) {
    Copy-Item -Force $macZip (Join-Path $macDir ("SistemaRampazzo-mac-" + $Version + ".zip"))
} else {
    Write-Warning "No se encontro artifact de macOS."
}

if (Test-Path $tmpDir) {
    Remove-Item -Recurse -Force $tmpDir
}

Write-Host ""
Write-Host "============================================"
Write-Host "  PROCESO FINALIZADO"
Write-Host "============================================"
Write-Host "  $winDir"
Write-Host "  $linuxDir"
Write-Host "  $macDir"
Write-Host "============================================"
Write-Host ""
Write-Host "Listo."
