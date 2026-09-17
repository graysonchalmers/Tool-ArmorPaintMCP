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
# Phase 1: the tool is actually registered on the MCP server object a client
# talks to (importing the function proves nothing about the MCP layer). No
# ArmorPaint and no config needed -- registration happens at import time.
Probe "reexport_project registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'reexport_project' in names, names; print(names)" }
Probe "inspect_project registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'inspect_project' in names, names; print(names)" }
Probe "run_script registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'run_script' in names, names; print(names)" }

# Phase 5: 7 mesh/UV editing tools, all registered on the MCP server object
# same as above -- no ArmorPaint and no config needed, registration happens
# at import time.
Probe "decimate_mesh registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'decimate_mesh' in names, names; print(names)" }
Probe "bevel_mesh registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'bevel_mesh' in names, names; print(names)" }
Probe "subdivide_mesh registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'subdivide_mesh' in names, names; print(names)" }
Probe "smooth_mesh registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'smooth_mesh' in names, names; print(names)" }
Probe "duplicate_mesh registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'duplicate_mesh' in names, names; print(names)" }
Probe "merge_mesh_geometry registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'merge_mesh_geometry' in names, names; print(names)" }
Probe "unwrap_mesh_uvs registered as an MCP tool" { & $Python -c "import asyncio; from armorpaint_mcp.server import mcp; names = [t.name for t in asyncio.run(mcp.list_tools())]; assert 'unwrap_mesh_uvs' in names, names; print(names)" }

Write-Host "-- $pass passed, $fail failed --"
Add-Content -Path $Log -Value "-- $pass passed, $fail failed --"
if ($fail -gt 0) {
    Write-Host "SMOKE FAILED"
    exit 1
}
Write-Host "SMOKE OK"
exit 0
