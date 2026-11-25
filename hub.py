#!/usr/bin/env python3
"""Agent Hub CLI — lets an agent report work to the Agent Hub dashboard and read
what the user confirmed there. Standard library + git only.

Setup (once per machine / cloud run):
    git clone https://github.com/guneytamer/agent-hub-data.git ~/agent-hub-data
    export HUB_DIR=~/agent-hub-data HUB_AGENT=career-agent

Commands:
    hub.py init  --name "Career Agent" [--description "..."]
    hub.py status working|idle|blocked|done "one-line summary"
    hub.py add "title" [--you] [--detail "..."] [--link URL] [--state STATE]
    hub.py update TASK_ID [--state STATE] [--log "msg"] [--title ..] [--detail ..] [--link ..]
    hub.py log TASK_ID "message"
    hub.py check            # what the user confirmed / rejected / asked since last check
    hub.py list             # this agent's tasks merged with the user's responses
    hub.py show TASK_ID

Task states: todo, doing, done, blocked, needs-you (a task for the user to do/approve).
The user answers needs-you tasks on the dashboard with confirm or reject (+ note).

Every write does: git pull --rebase -> edit agents/<agent>.json -> commit -> push.
Use --no-push to batch several edits, then `hub.py push`.
"""
import argparse
import datetime as dt
import glob
import json
import os
import random
import string
import subprocess
import sys
import time

STATES = ["todo", "doing", "done", "blocked", "needs-you"]
STATUSES = ["working", "idle", "blocked", "done"]


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def die(msg):
    print(f"hub: {msg}", file=sys.stderr)
    sys.exit(1)


def git(hub, *args, check=True):
    r = subprocess.run(["git", "-C", hub, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        die(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r


def pull(hub):
    git(hub, "pull", "--rebase", "--quiet", check=False)


def push(hub, msg):
    git(hub, "add", "-A")
    if git(hub, "diff", "--cached", "--quiet", check=False).returncode == 0:
        return
    git(hub, "commit", "--quiet", "-m", msg)
    for attempt in range(4):
        r = git(hub, "push", "--quiet", check=False)
        if r.returncode == 0:
            return
        time.sleep(1 + attempt)
        git(hub, "pull", "--rebase", "--quiet", check=False)
    die("push failed after retries — run `hub.py push` later")


def paths(hub, agent):
    return (os.path.join(hub, "agents", f"{agent}.json"),
            os.path.join(hub, "responses", f"{agent}.json"))


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"hub: warning: {path} is not valid JSON ({e}); ignoring it", file=sys.stderr)
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def new_id():
    return "t-" + dt.datetime.now().strftime("%m%d") + "-" + "".join(
        random.choices(string.ascii_lowercase + string.digits, k=4))


def find(doc, tid):
    for t in doc["tasks"]:
        if t["id"] == tid:
            return t
    die(f"no task {tid}")


DATA_URL = "https://github.com/guneytamer/agent-hub-data.git"


def project_config():
    """Optional hub.json in the current directory: {"agent": "career-agent"}."""
    try:
        with open("hub.json") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def find_hub():
    """Find an agent-hub-data clone near here; clone it to ~/agent-hub-data if none."""
    cands = [os.path.join(os.getcwd(), "..", "agent-hub-data"), "~/agent-hub-data"]
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    if top:
        cands.insert(0, os.path.join(os.path.dirname(top), "agent-hub-data"))
    for root in ("~", "/home", "/workspace", "/workspaces", "/repos", "/tmp"):
        root = os.path.expanduser(root)
        for depth_glob in ("agent-hub-data", "*/agent-hub-data", "*/*/agent-hub-data"):
            cands += glob.glob(os.path.join(root, depth_glob))
    for c in cands:
        c = os.path.abspath(os.path.expanduser(c))
        if os.path.isdir(os.path.join(c, ".git")):
            return c
    dest = os.path.expanduser("~/agent-hub-data")
    r = subprocess.run(["git", "clone", "--quiet", DATA_URL, dest], capture_output=True, text=True)
    if r.returncode == 0:
        return dest
    die(f"no agent-hub-data clone found and `git clone {DATA_URL}` failed:\n{r.stderr.strip()}")


def main():
    cfg = project_config()
    p = argparse.ArgumentParser(description="Agent Hub CLI")
    p.add_argument("--hub", default=os.environ.get("HUB_DIR") or cfg.get("hub"), help="path to agent-hub-data clone (or $HUB_DIR; auto-found if unset)")
    p.add_argument("--agent", default=os.environ.get("HUB_AGENT") or cfg.get("agent"), help="agent id, e.g. career-agent (or $HUB_AGENT, or hub.json)")
    p.add_argument("--no-push", action="store_true", help="edit locally without committing/pushing")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init"); s.add_argument("--name"); s.add_argument("--description", default="")
    s = sub.add_parser("status"); s.add_argument("status", choices=STATUSES); s.add_argument("summary", nargs="?", default=None)
    s = sub.add_parser("add"); s.add_argument("title"); s.add_argument("--you", action="store_true", help="task for the user (needs-you)")
    s.add_argument("--detail", default=""); s.add_argument("--link", default=""); s.add_argument("--state", choices=STATES)
    s = sub.add_parser("update"); s.add_argument("id"); s.add_argument("--state", choices=STATES)
    s.add_argument("--log"); s.add_argument("--title"); s.add_argument("--detail"); s.add_argument("--link")
    s = sub.add_parser("log"); s.add_argument("id"); s.add_argument("message")
    s = sub.add_parser("check"); s.add_argument("--peek", action="store_true", help="don't mark responses as seen")
    sub.add_parser("list")
    s = sub.add_parser("show"); s.add_argument("id")
    sub.add_parser("push")
    a = p.parse_args()

    if not a.agent:
        die("set HUB_AGENT (e.g. career-agent), pass --agent, or put {\"agent\": \"...\"} in ./hub.json")
    if not a.hub:
        a.hub = find_hub()
    hub = os.path.expanduser(a.hub)
    if not os.path.isdir(os.path.join(hub, ".git")):
        die(f"{hub} is not a git clone of agent-hub-data")

    pull(hub)
    apath, rpath = paths(hub, a.agent)
    doc = load(apath, None)
    resp = load(rpath, {"responses": {}, "messages": []})

    if a.cmd == "push":
        push(hub, f"{a.agent}: sync"); print("pushed"); return

    if doc is None:
        if a.cmd != "init":
            die(f"agent '{a.agent}' not registered — run: hub.py init --name \"Display Name\"")
        doc = {"agent": a.agent, "name": a.name or a.agent, "description": a.description,
               "status": "idle", "summary": "", "updated": now(), "tasks": [], "seen": {}}
        save(apath, doc)
        if not a.no_push:
            push(hub, f"{a.agent}: register")
        print(f"registered {a.agent}"); return

    changed, msg = False, a.cmd
    if a.cmd == "init":
        if a.name: doc["name"] = a.name
        if a.description: doc["description"] = a.description
        changed, msg = True, "update profile"
        print("profile updated")
    elif a.cmd == "status":
        doc["status"] = a.status
        if a.summary is not None:
            doc["summary"] = a.summary
        changed, msg = True, f"status {a.status}"
        print(f"status: {a.status}")
    elif a.cmd == "add":
        state = a.state or ("needs-you" if a.you else "todo")
        t = {"id": new_id(), "title": a.title, "detail": a.detail, "link": a.link,
             "owner": "you" if (a.you or state == "needs-you") else "agent",
             "state": state, "created": now(), "updated": now(), "log": []}
        doc["tasks"].append(t)
        changed, msg = True, f"add {t['id']}"
        print(t["id"])
    elif a.cmd in ("update", "log"):
        t = find(doc, a.id)
        if a.cmd == "log":
            t["log"].append({"at": now(), "msg": a.message})
        else:
            for k in ("title", "detail", "link"):
                if getattr(a, k) is not None:
                    t[k] = getattr(a, k)
            if a.state:
                t["state"] = a.state
                if a.state == "needs-you":
                    t["owner"] = "you"
            if a.log:
                t["log"].append({"at": now(), "msg": a.log})
        t["updated"] = now()
        changed, msg = True, f"update {a.id}"
        print(f"{a.id}: {t['state']}")
    elif a.cmd == "check":
        seen = doc.setdefault("seen", {})
        new = []
        for tid, r in resp.get("responses", {}).items():
            if seen.get(tid) != r.get("at"):
                new.append((tid, r))
        msgs = [m for m in resp.get("messages", []) if m.get("at", "") > seen.get("_messages", "")]
        titles = {t["id"]: t["title"] for t in doc["tasks"]}
        if not new and not msgs:
            print("nothing new from the user")
        for tid, r in new:
            note = f" — note: {r['note']}" if r.get("note") else ""
            print(f"[{r['decision'].upper()}] {tid} {titles.get(tid, '(unknown task)')} at {r['at']}{note}")
        for m in msgs:
            print(f"[MESSAGE] {m['at']}: {m['text']}")
        if not a.peek and (new or msgs):
            for tid, r in new:
                seen[tid] = r["at"]
            if msgs:
                seen["_messages"] = max(m["at"] for m in msgs)
            changed, msg = True, "ack user responses"
    elif a.cmd in ("list", "show"):
        rs = resp.get("responses", {})
        tasks = doc["tasks"] if a.cmd == "list" else [find(doc, a.id)]
        for t in tasks:
            r = rs.get(t["id"])
            eff = r["decision"] if r else t["state"]
            print(f"{t['id']}  [{eff}]  {t['title']}" + (f"  ({t['owner']})" if t["owner"] == "you" else ""))
            if a.cmd == "show":
                if t.get("detail"): print(f"  detail: {t['detail']}")
                if t.get("link"): print(f"  link: {t['link']}")
                for l in t["log"]: print(f"  {l['at']}  {l['msg']}")
                if r and r.get("note"): print(f"  user note: {r['note']}")
        if not tasks:
            print("no tasks")

    if changed:
        doc["updated"] = now()
        save(apath, doc)
        if not a.no_push:
            push(hub, f"{a.agent}: {msg}")


if __name__ == "__main__":
    main()
