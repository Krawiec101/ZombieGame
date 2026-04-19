Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Push-Location $repoRoot
try {
    Write-Host "==> docker compose build"
    docker compose build

    Write-Host "==> pip-audit"
    docker compose run --rm sca

    Write-Host "==> ruff"
    docker compose run --rm lint

    Write-Host "==> mypy"
    docker compose run --rm typecheck

    Write-Host "==> pytest + coverage"
    $pytestOutput = docker compose run --rm app pytest tests --ignore=mutants --ignore=tests/architecture --cov=src --cov-fail-under=95 --cov-report=term-missing --cov-report=xml:coverage.xml
    $pytestOutput | Set-Content -Path "pytest-coverage.txt"
    $pytestOutput

    Write-Host "==> CRAP gate"
    docker compose run --rm app python scripts/ci/crap_gate.py --coverage-xml coverage.xml --source-dir src --summary-md crap-summary.md

    Write-Host "==> architecture tests"
    $architectureOutput = docker compose run --rm app pytest -q tests/architecture
    $architectureOutput | Set-Content -Path "architecture-report.txt"
    $architectureOutput

    Write-Host "==> mutmut"
    docker compose run --rm app sh -lc "rm -rf mutants"
    docker compose run --rm app mutmut run
    $mutmutOutput = docker compose run --rm app sh -lc "mutmut results --all true"
    $mutmutOutput | Set-Content -Path "mutmut-results.txt"
    $mutmutOutput

    $resultsText = ($mutmutOutput -join "`n")
    $killed = ([regex]::Matches($resultsText, "(?im):\s*killed\s*$")).Count
    $survived = ([regex]::Matches($resultsText, "(?im):\s*survived\s*$")).Count
    $suspicious = ([regex]::Matches($resultsText, "(?im):\s*suspicious\s*$")).Count
    $timeout = ([regex]::Matches($resultsText, "(?im):\s*timeout\s*$")).Count
    $noTests = ([regex]::Matches($resultsText, "(?im):\s*(no tests|untested)\s*$")).Count
    $total = $killed + $survived + $suspicious + $timeout + $noTests
    if ($total -le 0) {
        throw "Unable to parse mutant statuses from mutmut results."
    }

    $score = [math]::Round(($killed / $total) * 100, 1)
    if ($score -le 92.0) {
        throw "Mutation score $score% <= 92.0%"
    }
    if ($suspicious -gt 0) {
        throw "Suspicious mutants $suspicious > 0"
    }
    if ($timeout -gt 1) {
        throw "Timeout mutants $timeout > 1"
    }

    Write-Host ("Mutation gate PASS: score={0}% killed={1} survived={2} suspicious={3} timeout={4} no_tests={5}" -f $score, $killed, $survived, $suspicious, $timeout, $noTests)
}
finally {
    Pop-Location
}
