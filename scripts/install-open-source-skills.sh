#!/usr/bin/env bash
# Installs the open-source sales-skills library (MIT) instead of storing copies in this repo.
# Usage: ./scripts/install-open-source-skills.sh [agent]   (default agent: claude-code)
set -euo pipefail
AGENT="${1:-claude-code}"
# Router skill only (recommended): routes any request to the right sales/GTM skill.
npx skills add sales-skills/sales --skill sales-do -a "$AGENT"
# To pull specific platform skills in one download, list them in a single --skill flag, e.g.:
# npx skills add sales-skills/sales --skill sales-cadence sales-call-review sales-deliverability -a "$AGENT"
