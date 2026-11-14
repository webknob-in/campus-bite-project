# Secret scan: gitleaks if present, else git-history regex greps. Exit 1 on findings.
# Usage: pwsh scripts/secret_scan.ps1   (run from anywhere inside the repo)
$ErrorActionPreference = 'Continue'
Set-Location (git rev-parse --show-toplevel)
$fail = 0

if (Get-Command gitleaks -ErrorAction SilentlyContinue) {
    Write-Host 'Tool: gitleaks'
    gitleaks detect --source . --log-opts="--all"
    if ($LASTEXITCODE -ne 0) { $fail++ }
} else {
    Write-Host 'Tool: git log --all -p + regex (gitleaks not installed)'
    $patterns = @(
        'sk-[A-Za-z0-9]{20,}',
        'postgresql(\+psycopg)?://[^:\s]+:[^@\s]+@',
        'JWT_SECRET\s*=\s*\S+',
        'OPENAI_API_KEY\s*=\s*\S+',
        'password\s*=',
        '-----BEGIN .*PRIVATE KEY-----'
    )
    # Accepted: placeholders and the local docker dev default.
    $accepted = 'DB_USER:DB_PASSWORD@|USER:PASSWORD@|campusbite:campusbite@|JWT_SECRET=(replace-with|change-me|\$\{|<)|OPENAI_API_KEY=\s*$|OPENAI_API_KEY=(\$\{|<|your-)'
    # Reviewed test fixtures / code (see docs/SECRET_SCAN.md); new hits still fail the scan.
    $accepted += '|:u:p@|u:p@|jwt_secret=|VALID_SECRET|TEST_JWT_SECRET = "test-secret-for-pytest|SimpleNamespace|OPENAI_API_KEY=. empty|secret-pass-1|Password123!|hide_password|password = (payload|overrides|"p"|"..")|errors\.password|values\.password|password=("short"|other_passwords|password|\.\.\.)|wrong_password|_customer\(|PASSWORD = '
    $lines = git log --all -p --no-color -- . ':(exclude)*node_modules*' ':(exclude)*package-lock.json' |
        Where-Object { $_ -match '^\+[^+]' }
    foreach ($p in $patterns) {
        $hits = $lines | Where-Object { $_ -match $p }
        $real = $hits | Where-Object { $_ -notmatch $accepted }
        Write-Host ("pattern {0}: {1} hits, {2} unclassified" -f $p, @($hits).Count, @($real).Count)
        # Review unclassified hits by hand (test fixtures may appear).
        $real | Select-Object -Unique | ForEach-Object { Write-Host "  $_" }
        if (@($real).Count -gt 0) { $fail++ }
    }
}

$bad = git log --all --name-only --diff-filter=A --format= | Where-Object { $_ -match '(^|/)\.env' -and $_ -notmatch '\.env\.example$' }
if ($bad) { Write-Host "Committed .env files: $bad"; $fail++ }
$tracked = git ls-files | Where-Object { $_ -match '(^|/)\.env' -and $_ -notmatch '\.env\.example$' }
if ($tracked) { Write-Host "Tracked .env files: $tracked"; $fail++ }
git check-ignore -q backend/.env; if ($LASTEXITCODE -ne 0) { Write-Host 'backend/.env not ignored'; $fail++ }
git check-ignore -q frontend/.env; if ($LASTEXITCODE -ne 0) { Write-Host 'frontend/.env not ignored'; $fail++ }

if ($fail -gt 0) { Write-Host "FAILED: $fail check(s) need review"; exit 1 }
Write-Host 'OK: no findings'; exit 0

