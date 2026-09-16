# smoke.ps1 -- headless proof the project is fundamentally alive.
# Contract: exit 0 = alive, non-zero = broken (with a one-line reason).
# Keep it FAST (seconds). Add one probe per phase; never delete a passing probe.

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("smoke_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmmss"))
$env:SMOKE = "1"  # gates diagnostic probes; production never sees them

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$pass = 0
$fail = 0

function Probe($name, [scriptblock]$cmd) {
    try {
        $output = & $cmd 2>&1
        $exit = $LASTEXITCODE
        Add-Content -Path $Log -Value "=== $name ===`n$output"
        if ($exit -eq 0 -or $null -eq $exit) {
            Write-Host "  [PASS] $name"
            $script:pass++
        } else {
            Write-Host "  [FAIL] $name (exit $exit) -- see $Log"
            $script:fail++
        }
    } catch {
        Add-Content -Path $Log -Value "=== $name ===`n$_"
        Write-Host "  [FAIL] $name -- see $Log"
        $script:fail++
    }
}

Write-Host "SMOKE -- $(Get-Date) -- $Root"
Add-Content -Path $Log -Value "SMOKE -- $(Get-Date) -- $Root"

# -- Phase 0 probes --------------------------------------------------
Probe "package imports" { & $Python -c "import armorpaint_mcp" }
Probe "--version exits 0" { & $Python -m armorpaint_mcp.server --version }
Probe "--help exits 0" { & $Python -m armorpaint_mcp.server --help }

# -- Phase N probes: add one per phase's headline feature -------------

Write-Host "-- $pass passed, $fail failed --"
Add-Content -Path $Log -Value "-- $pass passed, $fail failed --"
if ($fail -gt 0) {
    Write-Host "SMOKE FAILED"
    exit 1
}
Write-Host "SMOKE OK"
exit 0
