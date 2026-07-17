#!/usr/bin/env bash
# One-shot setup for Mac and Linux. Run this once from inside the project folder:
#   bash setup.sh
# It creates a private GitHub repo, pushes the project, stores your secrets,
# enables the daily run, and kicks off the first one. You only answer 3 prompts.

set -euo pipefail
say(){ printf "\n\033[1;33m%s\033[0m\n" "$1"; }
die(){ printf "\n\033[1;31m%s\033[0m\n" "$1"; exit 1; }

command -v git >/dev/null || die "Git isn't installed. Install it, then run this again."
if ! command -v gh >/dev/null; then
  die "The GitHub CLI 'gh' isn't installed. Install it once, then rerun:
  Mac:    brew install gh
  Ubuntu: sudo apt install gh
  Then:   bash setup.sh"
fi

# 1. Log in to GitHub (opens your browser once). Skips if already logged in.
gh auth status >/dev/null 2>&1 || { say "Step 1 of 4: log in to GitHub (a browser window will open)."; gh auth login; }

# 2. Ask for the only things that are yours.
say "Step 2 of 4: your details (nothing is stored on disk)."
read -rp "  Your developer.clashofclans.com email: " COC_EMAIL
read -rsp "  Your developer.clashofclans.com password: " COC_PASSWORD; echo
read -rp "  Your player tag(s), comma-separated, main first (e.g. #ABC,#DEF): " COC_PLAYER_TAGS
REPO_NAME="coc-tracker"
read -rp "  Repo name [coc-tracker]: " x; REPO_NAME="${x:-$REPO_NAME}"

# 3. Create the private repo and push everything.
say "Step 3 of 4: creating your private repo and uploading the project."
git init -q
git config --local user.name  "$(gh api user -q .login 2>/dev/null || echo coc-tracker)"
git config --local user.email "$(gh api user -q .login 2>/dev/null || echo coc-tracker)@users.noreply.github.com"
git add -A
git commit -qm "Initial commit" || true
gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

# Store secrets and let the daily job write back to the repo.
gh secret set COC_EMAIL        --body "$COC_EMAIL"
gh secret set COC_PASSWORD     --body "$COC_PASSWORD"
gh secret set COC_PLAYER_TAGS  --body "$COC_PLAYER_TAGS"
gh api --method PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=write -F can_approve_pull_request_reviews=true >/dev/null

# 4. Run it now and wait for the first result.
say "Step 4 of 4: running the first fetch (about a minute)."
gh workflow run track.yml
sleep 6
RUN_ID="$(gh run list --workflow track.yml --limit 1 --json databaseId -q '.[0].databaseId')"
gh run watch "$RUN_ID" --exit-status || die "The first run failed. Open the Actions tab in your repo to see why, or paste me the error."

say "Done. Your tracker is live and will run every day."
echo "  Repo:      https://github.com/$REPO"
echo "  Dashboard: open dashboard.html in the repo, download it, open in your browser."
echo "  Defenses:  drop a village.json into data/accounts/<YOURTAG>/ later (see village.example.json)."
