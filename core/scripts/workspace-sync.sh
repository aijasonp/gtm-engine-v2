#!/usr/bin/env bash
# Sync the GTM agent workspace to example-org/openclaw-workspaces (push-only).
# Follows the repo README sync model:
#   - Push-only: local workspace is always the source of truth; never pull.
#   - Allowlist-only sync of core workspace .md files into gtm-agent/.
#   - Excludes: memory/ (daily logs, private context), credentials, skills/,
#     scripts/, account-knowledge/, and any file not on the allowlist.
set -euo pipefail

WORKSPACE="$HOME/.openclaw/workspace"
REPO_DIR="$HOME/.openclaw/repos/openclaw-workspaces"
AGENT_DIR="gtm-agent"
BRANCH="main"

# Touch the log on every run so cron-health-monitor sees a fresh mtime even
# when the script produces no output (NO_CHANGES path exits before echo).
# Missing/stale log = false-positive alert, {{ADMIN_1}} 2026-10-13.
LOG_FILE="$WORKSPACE/scripts/logs/workspace-sync.log"
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

# Allowlist per repo README (SECURITY.md + workflows/orgloop-dev.md don't exist
# in this workspace; skipped automatically below).
# PROJECTS.md + RUNBOOK.md and the references/ + rules/ directories added
# 2026-10-13 with {{ADMIN_1}}'s approval — operational specs, no credentials
# (secret-value scanned before adding).
FILES=(
  "AGENTS.md"
  "SOUL.md"
  "TOOLS.md"
  "IDENTITY.md"
  "USER.md"
  "HEARTBEAT.md"
  "MEMORY.md"
  "SECURITY.md"
  "PROJECTS.md"
  "RUNBOOK.md"
  "workflows/orgloop-dev.md"
)

DIRS=(
  "references"
  "rules"
)

# Git identity (matches previous gtm-agent commits)
GIT_NAME="GTM agent (OpenClaw)"
GIT_EMAIL="rep@example.com"

# Fresh GitHub App token for push auth
TOKEN="$("$HOME/.config/github-app/refresh-token.sh" 2>/dev/null | tail -1)"
if [ -z "$TOKEN" ]; then
  echo "FAILED: could not mint GitHub App token" >&2
  exit 1
fi
REMOTE_URL="https://x-access-token:${TOKEN}@github.com/example-org/openclaw-workspaces.git"

# Clone or refresh local repo copy
if [ -d "$REPO_DIR/.git" ]; then
  cd "$REPO_DIR"
  git remote set-url origin "$REMOTE_URL"
  git fetch origin "$BRANCH"
  # Abandon any leftover local branch/rebase state; always sync from main.
  git rebase --abort >/dev/null 2>&1 || true
  git checkout -B "$BRANCH" "origin/$BRANCH" >/dev/null 2>&1
  git reset --hard "origin/$BRANCH" >/dev/null
else
  rm -rf "$REPO_DIR"
  git clone "$REMOTE_URL" "$REPO_DIR" >/dev/null
  cd "$REPO_DIR"
  git checkout "$BRANCH" >/dev/null 2>&1
fi

git config user.name "$GIT_NAME"
git config user.email "$GIT_EMAIL"

mkdir -p "$AGENT_DIR"

COPIED=()
SKIPPED=()
for file in "${FILES[@]}"; do
  src="$WORKSPACE/$file"
  dst="$REPO_DIR/$AGENT_DIR/$file"
  if [ -f "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    COPIED+=("$file")
  else
    SKIPPED+=("$file")
  fi
done

# Remove previously-synced allowlist files that no longer exist locally
# (keeps gtm-agent/ mirror honest for the allowlisted set only).
for file in "${FILES[@]}"; do
  dst="$REPO_DIR/$AGENT_DIR/$file"
  if [ ! -f "$WORKSPACE/$file" ] && [ -f "$dst" ]; then
    rm -f "$dst"
  fi
done

# Sync allowlisted directories (--delete keeps the mirror honest)
for dir in "${DIRS[@]}"; do
  src="$WORKSPACE/$dir/"
  dst="$REPO_DIR/$AGENT_DIR/$dir/"
  if [ -d "$src" ]; then
    mkdir -p "$dst"
    rsync -a --delete "$src" "$dst"
    COPIED+=("$dir/")
  else
    SKIPPED+=("$dir/")
  fi
done

git add -A -- "$AGENT_DIR"

if git diff --cached --quiet; then
  echo "NO_CHANGES: allowlist files identical to repo"
  exit 0
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M UTC')
git commit -m "gtm-agent workspace sync: ${TIMESTAMP}" \
  --author="$GIT_NAME <$GIT_EMAIL>" >/dev/null

# Other agents push to this repo on their own schedules; retry rebase+push
# to ride over non-fast-forward rejections.
PUSHED=0
for attempt in 1 2 3 4 5; do
  git fetch origin "$BRANCH" >/dev/null 2>&1
  if git rebase "origin/$BRANCH" >/dev/null 2>&1 && git push origin "$BRANCH" >/dev/null 2>&1; then
    PUSHED=1
    break
  fi
  git rebase --abort >/dev/null 2>&1 || true
  sleep $((attempt * 5))
done

if [ "$PUSHED" -ne 1 ]; then
  echo "FAILED: push rejected after 5 rebase attempts" >&2
  exit 1
fi

echo "COMPLETED: pushed gtm-agent workspace sync (${#COPIED[@]} files: ${COPIED[*]})"
if [ "${#SKIPPED[@]}" -gt 0 ]; then
  echo "NOTE: skipped missing files: ${SKIPPED[*]}"
fi
