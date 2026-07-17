# One-shot setup for Windows. Run this once from inside the project folder:
#   Right-click the folder > "Open in Terminal", then:  ./setup.ps1
# It creates a private GitHub repo, pushes the project, stores your secrets,
# enables the daily run, and starts the first one. You answer 3 prompts.

$ErrorActionPreference = "Stop"
function Say($m){ Write-Host "`n$m" -ForegroundColor Yellow }
function Die($m){ Write-Host "`n$m" -ForegroundColor Red; exit 1 }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "Git isn't installed. Install it, then rerun." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue))  { Die "The GitHub CLI 'gh' isn't installed. Install once with:  winget install GitHub.cli   then rerun ./setup.ps1" }

# 1. Log in to GitHub (opens your browser once).
gh auth status 2>$null; if ($LASTEXITCODE -ne 0) { Say "Step 1 of 4: log in to GitHub (a browser window opens)."; gh auth login }

# 2. Your details.
Say "Step 2 of 4: your details (nothing is stored on disk)."
$COC_EMAIL = Read-Host "  Your developer.clashofclans.com email"
$sec = Read-Host "  Your developer.clashofclans.com password" -AsSecureString
$COC_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
$COC_PLAYER_TAGS = Read-Host "  Your player tag(s), comma-separated, main first (e.g. #ABC,#DEF)"
$REPO_NAME = Read-Host "  Repo name [coc-tracker]"; if ([string]::IsNullOrWhiteSpace($REPO_NAME)) { $REPO_NAME = "coc-tracker" }

# 3. Create private repo and push.
Say "Step 3 of 4: creating your private repo and uploading the project."
git init -q
$login = (gh api user -q .login)
git config --local user.name  $login
git config --local user.email "$login@users.noreply.github.com"
git add -A
git commit -qm "Initial commit" 2>$null
gh repo create $REPO_NAME --private --source=. --remote=origin --push
$REPO = (gh repo view --json nameWithOwner -q .nameWithOwner)

gh secret set COC_EMAIL       --body "$COC_EMAIL"
gh secret set COC_PASSWORD    --body "$COC_PASSWORD"
gh secret set COC_PLAYER_TAGS --body "$COC_PLAYER_TAGS"
gh api --method PUT "repos/$REPO/actions/permissions/workflow" -f default_workflow_permissions=write -F can_approve_pull_request_reviews=true | Out-Null

# 4. First run.
Say "Step 4 of 4: running the first fetch (about a minute)."
gh workflow run track.yml
Start-Sleep -Seconds 6
$RUN_ID = (gh run list --workflow track.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --exit-status; if ($LASTEXITCODE -ne 0) { Die "The first run failed. Open the Actions tab in your repo, or paste me the error." }

Say "Done. Your tracker is live and will run every day."
Write-Host "  Repo:      https://github.com/$REPO"
Write-Host "  Dashboard: open dashboard.html in the repo, download it, open in your browser."
Write-Host "  Defenses:  drop a village.json into data/accounts/<YOURTAG>/ later (see village.example.json)."
