param(
  [string]$HostName = "154.217.247.39",
  [int]$Port = 28,
  [string]$User = "root",
  [string]$AppDir = "/data/wwwroot/AIHot",
  [string]$Branch = "codex/precise-review-model-v1",
  [string]$KeyPath = $env:AIHOT_DEPLOY_KEY,
  [string]$RemoteBundle = "/tmp/aihot-deploy.bundle",
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Assert-NativeCommandSucceeded([string]$Step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE."
  }
}

if (-not $KeyPath) {
  throw "Provide -KeyPath or set AIHOT_DEPLOY_KEY. Do not put private keys in this script."
}

if (-not (Test-Path -LiteralPath $KeyPath)) {
  throw "SSH key not found: $KeyPath"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$currentBranch = (git branch --show-current).Trim()
Assert-NativeCommandSucceeded "Read current Git branch"
if ($currentBranch -ne $Branch) {
  throw "Current branch is '$currentBranch', expected '$Branch'."
}

if (-not $SkipBuild) {
  Push-Location (Join-Path $repoRoot "web")
  try {
    npm run build
    Assert-NativeCommandSucceeded "Build frontend"
  } finally {
    Pop-Location
  }
}

$commit = (git rev-parse HEAD).Trim()
Assert-NativeCommandSucceeded "Resolve deployment commit"
$bundlePath = Join-Path ([System.IO.Path]::GetTempPath()) "aihot-$commit.bundle"

if (Test-Path -LiteralPath $bundlePath) {
  Remove-Item -LiteralPath $bundlePath -Force
}

git bundle create $bundlePath HEAD
Assert-NativeCommandSucceeded "Create deployment bundle"

$sshTarget = "$User@$HostName"
$sshArgs = @("-i", $KeyPath, "-p", "$Port", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new")
$scpArgs = @("-i", $KeyPath, "-P", "$Port", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new")

scp @scpArgs $bundlePath "${sshTarget}:$RemoteBundle"
Assert-NativeCommandSucceeded "Upload deployment bundle"

$remoteScript = @"
set -euo pipefail
cd "$AppDir"
backup_dir="/data/wwwroot/AIHot-deploy-backups/`$(date +%Y%m%d%H%M%S)"
mkdir -p "`$backup_dir"
git status --short --branch > "`$backup_dir/status.txt" || true
git diff > "`$backup_dir/worktree.diff" || true
git diff --cached > "`$backup_dir/index.diff" || true
git ls-files --others --exclude-standard > "`$backup_dir/untracked.txt" || true

git fetch "$RemoteBundle" HEAD
git reset --hard "$commit"
git clean -fd

.venv/bin/python -m pip install -e .
.venv/bin/python -m alembic upgrade head
.venv/bin/intel-engine seed-sources

systemctl restart aihot-web.service
systemctl is-active --quiet aihot-web.service
for i in `$(seq 1 15); do
  if curl -fsS http://127.0.0.1:8003/health; then
    exit 0
  fi
  sleep 2
done
systemctl status aihot-web.service --no-pager -l || true
exit 1
"@

$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
ssh @sshArgs $sshTarget "printf '%s' '$encoded' | base64 -d | bash"
Assert-NativeCommandSucceeded "Run remote deployment"

Write-Host "Deployed $commit to ${sshTarget}:$AppDir"
