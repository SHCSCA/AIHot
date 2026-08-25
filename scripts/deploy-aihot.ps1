param(
  [string]$HostName = "154.217.247.39",
  [int]$Port = 28,
  [string]$User = "root",
  [string]$AppDir = "/data/wwwroot/AIHot",
  [string]$Branch = "codex/precise-review-model-v1",
  [string]$KeyPath = $env:AIHOT_DEPLOY_KEY,
  [string]$RemoteBundle = "/tmp/aihot-deploy.bundle",
  [int]$PipelineBatchLimit = 1000,
  [int]$PipelineSmokeLimit = 1,
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Assert-NativeCommandSucceeded([string]$Step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE."
  }
}

function Assert-CleanTrackedWorktree {
  $trackedChanges = @(git status --porcelain --untracked-files=no)
  Assert-NativeCommandSucceeded "Inspect tracked worktree"
  if ($trackedChanges.Count -gt 0) {
    throw "Tracked worktree changes exist. Commit them before deployment."
  }
}

function Assert-RequiredFilesCommitted {
  $requiredFiles = @(
    "config/collection.yaml",
    "channels/catalogs/ai_expansion.yaml",
    "channels/catalogs/amazon_expansion.yaml",
    "migrations/versions/20260728_0008_event_evidence_assessments.py",
    "migrations/versions/20260825_0009_ai_analysis_settings.py",
    "src/intel_engine/corroboration.py",
    "src/intel_engine/rules.py",
    "src/intel_engine/system_settings.py"
  )
  foreach ($requiredFile in $requiredFiles) {
    git cat-file -e "HEAD:$requiredFile"
    if ($LASTEXITCODE -ne 0) {
      throw "Required deployment file is not committed in HEAD: $requiredFile"
    }
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

Assert-CleanTrackedWorktree
Assert-RequiredFilesCommitted

if (-not $SkipBuild) {
  Push-Location (Join-Path $repoRoot "web")
  try {
    npm run build
    Assert-NativeCommandSucceeded "Build frontend"
  } finally {
    Pop-Location
  }
  Assert-CleanTrackedWorktree
}

$commit = (git rev-parse HEAD).Trim()
Assert-NativeCommandSucceeded "Resolve deployment commit"
$remoteCommitLine = @(git ls-remote origin "refs/heads/$Branch")
Assert-NativeCommandSucceeded "Resolve remote deployment branch"
$remoteCommit = if ($remoteCommitLine.Count -gt 0) {
  ($remoteCommitLine[0] -split "\s+")[0]
} else {
  ""
}
if ($remoteCommit -ne $commit) {
  throw "Remote branch '$Branch' is at '$remoteCommit', expected '$commit'. Push before deployment."
}
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

systemctl disable --now aihot-pipeline.timer >/dev/null 2>&1 || true
systemctl stop aihot-pipeline.service >/dev/null 2>&1 || true
systemctl stop 'aihot-pipeline@*.service' >/dev/null 2>&1 || true
if systemctl list-units \
  --type=service \
  --state=active,activating,deactivating \
  --no-legend \
  'aihot-pipeline*.service' | grep -q .; then
  systemctl list-units \
    --type=service \
    --state=active,activating,deactivating \
    --no-pager \
    'aihot-pipeline*.service'
  exit 1
fi

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
.venv/bin/intel-engine backfill-evidence

test -f "$AppDir/.env"
pipeline_user="`$(systemctl show aihot-web.service --property=User --value)"
if [ -z "`$pipeline_user" ] || [ "`$pipeline_user" = "root" ]; then
  pipeline_user="www-data"
fi
id "`$pipeline_user" >/dev/null

rm -f /etc/systemd/system/aihot-pipeline.service

cat > /etc/systemd/system/aihot-pipeline@.service <<UNIT
[Unit]
Description=AIHot scheduled intelligence pipeline
After=network-online.target aihot-web.service
Wants=network-online.target

[Service]
Type=oneshot
User=`$pipeline_user
WorkingDirectory=$AppDir
EnvironmentFile=$AppDir/.env
Environment=INTEL_ENV_FILE=
ExecStart=$AppDir/.venv/bin/intel-engine pipeline-once --worker-id systemd-pipeline-%i --limit %i
Nice=5
TimeoutStartSec=120min
NoNewPrivileges=true
PrivateTmp=true
UNIT

cat > /etc/systemd/system/aihot-pipeline.timer <<'UNIT'
[Unit]
Description=Scan AIHot due sources daily at 01:00

[Timer]
OnCalendar=*-*-* 01:00
Persistent=true
RandomizedDelaySec=300
Unit=aihot-pipeline@$PipelineBatchLimit.service

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl restart aihot-web.service
systemctl is-active --quiet aihot-web.service
for i in `$(seq 1 15); do
  if curl -fsS http://127.0.0.1:8003/health; then
    smoke_unit="aihot-pipeline@$PipelineSmokeLimit.service"
    systemctl reset-failed "`$smoke_unit" >/dev/null 2>&1 || true
    if ! systemctl start "`$smoke_unit"; then
      systemctl status "`$smoke_unit" --no-pager -l || true
      journalctl -u "`$smoke_unit" -n 80 --no-pager || true
      exit 1
    fi
    pipeline_result="`$(systemctl show "`$smoke_unit" --property=Result --value)"
    pipeline_exit="`$(systemctl show "`$smoke_unit" --property=ExecMainStatus --value)"
    [ "`$pipeline_result" = "success" ] && [ "`$pipeline_exit" = "0" ] || exit 1
    systemctl enable --now aihot-pipeline.timer
    systemctl is-active --quiet aihot-pipeline.timer
    exit 0
  fi
  sleep 2
done
systemctl status aihot-web.service --no-pager -l || true
exit 1
"@

$normalizedRemoteScript = $remoteScript -replace "`r",""
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($normalizedRemoteScript))
ssh @sshArgs $sshTarget "printf '%s' '$encoded' | base64 -d | bash"
Assert-NativeCommandSucceeded "Run remote deployment"

Write-Host "Deployed $commit to ${sshTarget}:$AppDir"
