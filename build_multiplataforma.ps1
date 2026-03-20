param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$Repo = "",
    [string]$Branch = "",
    [switch]$PurgeArtifactsBeforeRun = $true
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

function Get-RepoArtifacts {
    param(
        [string]$GhPath,
        [string]$Repository
    )
    $all = @()
    $page = 1
    while ($true) {
        $raw = & $GhPath api "repos/$Repository/actions/artifacts?per_page=100&page=$page" 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) { break }
        try {
            $obj = $raw | ConvertFrom-Json
            $items = @($obj.artifacts)
            if ($items.Count -eq 0) { break }
            $all += $items
            if ($items.Count -lt 100) { break }
            $page += 1
        } catch {
            break
        }
    }
    return $all
}

function Purge-RepoArtifacts {
    param(
        [string]$GhPath,
        [string]$Repository
    )
    $artifacts = Get-RepoArtifacts -GhPath $GhPath -Repository $Repository
    if (-not $artifacts -or @($artifacts).Count -eq 0) {
        Write-Host "      No hay artifacts previos para limpiar."
        return
    }

    $count = @($artifacts).Count
    $bytes = 0
    foreach ($a in @($artifacts)) { $bytes += [int64]($a.size_in_bytes) }
    $mb = [math]::Round($bytes / 1MB, 1)
    Write-Host "      Artifacts actuales: $count (~$mb MB)"

    $deleted = 0
    foreach ($a in @($artifacts)) {
        & $GhPath api -X DELETE "repos/$Repository/actions/artifacts/$($a.id)" 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) { $deleted += 1 }
    }
    Write-Host "      Artifacts eliminados: $deleted"
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

function Test-RemoteBranch {
    param(
        [string]$GhPath,
        [string]$Repository,
        [string]$BranchName
    )
    if ([string]::IsNullOrWhiteSpace($BranchName)) { return $false }
    & $GhPath api "repos/$Repository/branches/$BranchName" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Get-RemoteAppVersion {
    param(
        [string]$GhPath,
        [string]$Repository,
        [string]$BranchName
    )
    try {
        $raw = & $GhPath api "repos/$Repository/contents/config.py?ref=$BranchName" 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) { return "" }
        $obj = $raw | ConvertFrom-Json
        if (-not $obj.content) { return "" }
        $b64 = [string]$obj.content
        $b64 = $b64 -replace "\s", ""
        $bytes = [System.Convert]::FromBase64String($b64)
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)
        $m = [regex]::Match($text, 'APP_VERSION\s*=\s*"([^"]+)"')
        if ($m.Success) { return $m.Groups[1].Value }
        return ""
    } catch {
        return ""
    }
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
$branchProvided = -not [string]::IsNullOrWhiteSpace($Branch)
$branchSource = "provided"
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
    $branchSource = "local-current-branch"
    try {
        $localBranch = (& git rev-parse --abbrev-ref HEAD 2>$null).Trim()
    } catch {
        $localBranch = ""
    }
    if (-not [string]::IsNullOrWhiteSpace($localBranch) -and $localBranch -ne "HEAD" -and
        (Test-RemoteBranch -GhPath $gh -Repository $Repo -BranchName $localBranch)) {
        $Branch = $localBranch
    }
}
if ([string]::IsNullOrWhiteSpace($Branch)) {
    $branchSource = "default-branch"
    try {
        $branchJson = & $gh repo view $Repo --json defaultBranchRef | ConvertFrom-Json
        $Branch = $branchJson.defaultBranchRef.name
    } catch {
        $Branch = ""
    }
}
if (-not (Test-RemoteBranch -GhPath $gh -Repository $Repo -BranchName $Branch)) {
    if ($branchProvided) {
        throw "La rama '$Branch' no existe en el repositorio '$Repo'."
    }
    $fallbackBranches = @("master", "main", "develop")
    foreach ($candidate in $fallbackBranches) {
        if (Test-RemoteBranch -GhPath $gh -Repository $Repo -BranchName $candidate) {
            $Branch = $candidate
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($Branch)) {
        throw "No se pudo detectar una rama valida para '$Repo'. Pasar -Branch explicitamente."
    }
}
Write-Host "      Repo: $Repo"
Write-Host "      Rama: $Branch"
Write-Host ""

Step "[2.2/8] Validando APP_VERSION remota contra version solicitada..."
$remoteAppVersion = Get-RemoteAppVersion -GhPath $gh -Repository $Repo -BranchName $Branch
if ([string]::IsNullOrWhiteSpace($remoteAppVersion)) {
    throw "No se pudo detectar APP_VERSION en config.py de '$Repo@$Branch'."
}
if ($remoteAppVersion -ne $Version) {
    throw (
        "Version inconsistente: solicitaste '$Version' pero la rama remota '$Branch' tiene APP_VERSION='$remoteAppVersion'. " +
        "Actualizar config.py en esa rama, push y reintentar."
    )
}
Write-Host "      OK (APP_VERSION remota = $remoteAppVersion)"
Write-Host ""

if ($PurgeArtifactsBeforeRun) {
    Step "[2.1/8] Liberando cuota de artifacts en GitHub..."
    Purge-RepoArtifacts -GhPath $gh -Repository $Repo
    Write-Host ""
}

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
 $dispatchStartedAtUtc = (Get-Date).ToUniversalTime().AddSeconds(-10)
& $gh workflow run $workflow -R $Repo --ref $Branch
Ensure-Success "No se pudo disparar el workflow. Verificar permisos y nombre del workflow."
Write-Host "      Workflow disparado."
Write-Host ""

Step "[5/8] Obteniendo run_id..."
$runId = $null
$maxAttempts = 20
$sleepSeconds = 3
for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    $runsRaw = & $gh run list -R $Repo --workflow $workflow --branch $Branch --event workflow_dispatch --limit 20 --json databaseId,createdAt,status,conclusion,headBranch,event 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($runsRaw)) {
        try {
            $runs = $runsRaw | ConvertFrom-Json
            $runsArray = @($runs)
            $recentCandidates = @(
                $runsArray | Where-Object {
                    $_.databaseId -and
                    $_.event -eq "workflow_dispatch" -and
                    $_.headBranch -eq $Branch -and
                    $_.createdAt -and
                    ([datetime]$_.createdAt).ToUniversalTime() -ge $dispatchStartedAtUtc
                } | Sort-Object { [datetime]$_.createdAt } -Descending
            )

            if ($recentCandidates.Count -gt 0) {
                $runId = [string]$recentCandidates[0].databaseId
                break
            }
        } catch {}
    }
    Start-Sleep -Seconds $sleepSeconds
}
if ([string]::IsNullOrWhiteSpace($runId)) {
    throw "No se pudo obtener run_id del workflow. Reintentar en unos segundos."
}
Write-Host "      Run ID: $runId"
Write-Host ""

Step "[6/8] Esperando finalizacion..."
& $gh run watch $runId -R $Repo --exit-status
$runWatchExit = $LASTEXITCODE
if ($runWatchExit -ne 0) {
    $failedLogs = ""
    try {
        $failedLogs = & $gh run view $runId -R $Repo --log-failed 2>&1 | Out-String
    } catch {
        $failedLogs = ""
    }

    if ($failedLogs -match "Artifact storage quota has been hit") {
        throw (
            "El workflow fallo por cuota de artifacts de GitHub Actions. " +
            "Aunque se eliminen artifacts, GitHub recalcula uso cada 6-12 horas. " +
            "Reintentar mas tarde o liberar cuota adicional desde Settings > Billing/Actions."
        )
    }
    throw "El workflow termino con error. Revisar GitHub Actions (run id: $runId)."
}
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

$missingPlatforms = @()

if (Test-Path $winZip) {
    Copy-Item -Force $winZip (Join-Path $winDir ("SistemaRampazzo-win-" + $Version + ".zip"))
    Write-Host "      Windows: OK"
} else {
    $missingPlatforms += "Windows"
    Write-Host "      Windows: FALTANTE"
}
if (Test-Path $linuxZip) {
    Copy-Item -Force $linuxZip (Join-Path $linuxDir ("SistemaRampazzo-linux-" + $Version + ".zip"))
    Write-Host "      Linux:   OK"
} else {
    $missingPlatforms += "Linux"
    Write-Host "      Linux:   FALTANTE"
}
if (Test-Path $macZip) {
    Copy-Item -Force $macZip (Join-Path $macDir ("SistemaRampazzo-mac-" + $Version + ".zip"))
    Write-Host "      macOS:   OK"
} else {
    $missingPlatforms += "macOS"
    Write-Host "      macOS:   FALTANTE"
}

if (Test-Path $tmpDir) {
    Remove-Item -Recurse -Force $tmpDir
}

if ($missingPlatforms.Count -gt 0) {
    $platforms = $missingPlatforms -join ", "
    throw "Faltan artifacts de las siguientes plataformas: $platforms. El build multiplataforma no esta completo."
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
