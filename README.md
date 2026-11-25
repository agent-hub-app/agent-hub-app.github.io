# Agent Hub

A dashboard for tracking what your AI agents are doing, and for confirming the tasks they hand to you.

**Dashboard:** https://guneytamer.com/agent-hub/ · [demo with sample data](https://guneytamer.com/agent-hub/?demo)

## How it works

```
 agents ──git push──▶  agent-hub-data (private repo)  ◀──GitHub API── dashboard (this page)
        ◀─git pull──   agents/<id>.json     (agent writes)
                       responses/<id>.json  (you write: confirm / reject / notes / messages)
```

- This repo holds only the page and the CLI. **No data lives here.**
- All data is in the private repo `guneytamer/agent-hub-data`. Each file has one writer, so agents and the dashboard never overwrite each other.
- The page talks to GitHub straight from your browser with a fine-grained token that has access only to `agent-hub-data`. The token is saved only in that browser's localStorage.

## Dashboard setup (once per browser)

1. Create a token: GitHub → Settings → Developer settings → [Fine-grained tokens](https://github.com/settings/personal-access-tokens/new)
   - Repository access: **Only select repositories** → `agent-hub-data`
   - Permissions → Repository → **Contents: Read and write**
2. Open the dashboard and paste the token.

## Connecting an agent

Click **Connect agent** on the dashboard and paste the snippet into the agent's instructions, or use this one:

```bash
git clone https://github.com/guneytamer/agent-hub-data.git ~/agent-hub-data 2>/dev/null || git -C ~/agent-hub-data pull -q
curl -fsSL https://raw.githubusercontent.com/guneytamer/agent-hub/main/hub.py -o ~/hub.py
export HUB_DIR=~/agent-hub-data HUB_AGENT=career-agent
python3 ~/hub.py init --name "Career Agent"        # first time only
```

The agent needs git push access to `agent-hub-data`:
- **Local Claude Code:** works through your normal `gh`/git login.
- **Cloud routines:** add `guneytamer/agent-hub-data` as a repository on the routine (next to its own repo), so the session can clone and push it.

### CLI

| Command | What it does |
|---|---|
| `hub.py check` | Shows what you confirmed, rejected (with your note) or messaged since the last check, and marks them as seen. Run it at the start of every run. |
| `hub.py status working "summary"` | Sets the agent's status (`working`, `idle`, `blocked`, `done`) and one-line summary. |
| `hub.py add "title" [--detail ..] [--link ..]` | Adds an agent task (prints its id). |
| `hub.py add "title" --you --detail "steps"` | Adds a task for **you**. It appears under *Waiting on you* with Done / Reply buttons. |
| `hub.py update ID --state doing\|done\|blocked --log "msg"` | Moves a task and logs progress. |
| `hub.py log ID "msg"` | Adds a progress line. |
| `hub.py list` / `hub.py show ID` | Lists tasks merged with your responses. |

Each write runs `git pull --rebase`, edits `agents/<id>.json`, commits and pushes (with retries). Add `--no-push` to batch edits, then `hub.py push`.

## Files

- `index.html` — the whole dashboard (no build step, no dependencies).
- `hub.py` — the agent CLI (Python 3 standard library + git).
