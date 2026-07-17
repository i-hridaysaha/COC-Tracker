# Setup (about 3 minutes, once)

You need a free developer account at https://developer.clashofclans.com first
(just an email and password). Then run one script.

## Mac / Linux
1. Unzip this folder.
2. Open Terminal in the folder.
3. Run:  `bash setup.sh`

## Windows
1. Unzip this folder.
2. Right-click the folder > "Open in Terminal".
3. Run:  `./setup.ps1`

The script logs you into GitHub (one browser click), asks for your CoC
developer email, password, and player tag(s), then does everything else:
creates a private repo, uploads the project, stores your secrets, turns on the
daily run, and starts the first one. When it finishes it prints your repo link.

Open `dashboard.html` from the repo (download it, open in your browser). Set
builders, Gold Pass, and events right on the Planner page.

First time using the GitHub CLI? Install it once:
- Mac: `brew install gh`
- Windows: `winget install GitHub.cli`
- Ubuntu: `sudo apt install gh`
