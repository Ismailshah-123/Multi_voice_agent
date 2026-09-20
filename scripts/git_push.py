#!/usr/bin/env python3
"""One-command git setup + push for this project.

    python scripts/git_push.py                          # first run: sets everything up and pushes
    python scripts/git_push.py "Improve billing page"   # later runs: your commit message

Safe by design: it never handles your password or token (git uses your own sign-in), it keeps secrets and
heavy folders (.env, .venv, qdrant_data ...) out of git, it refuses files over GitHub's 100 MB limit,
it merges in whatever GitHub already has (like the README it created) and it never force-pushes.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REMOTE = "https://github.com/Ismailshah-123/Multi_voice_agent.git"
HEAVY_DIRS = {".venv", "venv", "qdrant_data", "__pycache__", "node_modules"}
MAX_BYTES = 95 * 1024 * 1024


def run(args, **kw):
    return subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=ROOT, text=True,
                          encoding="utf-8", errors="replace", **kw)


def git(*args, check=True, show=False):
    r = run(args, capture_output=not show)
    if check and r.returncode != 0:
        sys.exit(f"\n[x] git {' '.join(args[:2])} failed:\n{(r.stderr or '').strip()}")
    return r.returncode if show else (r.stdout or "").strip()


def ok(*args):
    return run(args, capture_output=True).returncode == 0


def blocked_root(path: str):
    """What to keep out of git if `path` is a secret or a heavy generated file, else None."""
    parts = path.split("/")
    for i, part in enumerate(parts[:-1]):
        if part in HEAVY_DIRS:
            return "/".join(parts[: i + 1])
    name = parts[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example") \
            or path.endswith(".streamlit/secrets.toml") or name.endswith(".pyc"):
        return path
    return None


def main():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit("[x] Git isn't installed. Get it from https://git-scm.com/downloads and run this again.")

    if not (ROOT / ".git").exists():
        git("init")
        git("symbolic-ref", "HEAD", "refs/heads/main")
        print("[ok] Created a new git repository (branch: main)")
    for key, prompt in (("user.name", "Your name for commits: "), ("user.email", "Your email for commits: ")):
        if not git("config", key, check=False):
            git("config", key, input(prompt).strip())

    git("add", "-A")
    roots = sorted({r for p in git("ls-files").splitlines() if (r := blocked_root(p))})
    if roots:
        git("rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", *roots)
        print("[!] Keeping out of git (files stay on your disk): " + ", ".join(roots))

    big = [p for p in git("diff", "--cached", "--name-only").splitlines()
           if (ROOT / p).is_file() and (ROOT / p).stat().st_size > MAX_BYTES]
    past = sorted({r for p in git("log", "--all", "--name-only", "--pretty=format:", check=False).splitlines()
                   if p and (r := blocked_root(p))})
    if big or past:
        git("reset", "-q", check=False)
        if big:
            print("[x] Over GitHub's 100 MB limit - add to .gitignore or delete:\n    " + "\n    ".join(big))
        if past:
            print("[x] Secrets/heavy files are already in earlier commits: " + ", ".join(past)
                  + "\n    If this repo was never pushed, delete the .git folder and run this script again for a clean start."
                  + "\n    If it WAS pushed, rotate those keys - they are in the history.")
        sys.exit(1)

    msg = " ".join(sys.argv[1:]).strip() or ("Update project" if ok("rev-parse", "--verify", "-q", "HEAD") else "Add voice agent platform")
    if not ok("diff", "--cached", "--quiet"):
        git("commit", "-q", "-m", msg)
        print("[ok] Committed:", git("log", "-1", "--pretty=%h %s"))
    else:
        print("[-] Nothing new to commit")

    if not git("remote", "get-url", "origin", check=False):
        url = os.environ.get("GIT_REMOTE_URL") or input(f"GitHub repo URL [Enter = {DEFAULT_REMOTE}]: ").strip() or DEFAULT_REMOTE
        if re.match(r"https?://[^/\s]*@", url):
            sys.exit("[x] Don't put a password or token in the URL. Use the plain URL - git opens a sign-in window instead.")
        git("remote", "add", "origin", url)

    branch = git("symbolic-ref", "--short", "HEAD")
    print(">> Checking what is already on GitHub ...")
    if git("fetch", "origin", show=True, check=False) != 0:
        sys.exit("[x] Couldn't reach GitHub. Check the repo URL and that you are signed in, then run this again.")
    theirs = f"origin/{branch}"
    if ok("rev-parse", "--verify", "-q", theirs) and not ok("merge-base", "--is-ancestor", theirs, "HEAD"):
        print(">> GitHub already has commits (like the README it created) - merging them in, nothing is overwritten")
        if git("merge", theirs, "--allow-unrelated-histories", "--no-edit", "-m", "Merge GitHub's initial commit", show=True, check=False) != 0:
            git("merge", "--abort", check=False)
            sys.exit("[x] GitHub has files that clash with yours (listed above). Nothing was changed or pushed.\n"
                     "    Easiest fix: delete those files on GitHub (or rename them), then run this again.")

    print(f">> Pushing '{branch}' to origin ...")
    if git("push", "-u", "origin", branch, show=True, check=False) != 0:
        sys.exit("\n[x] Push didn't go through (nothing was force-pushed). Read the message above:\n"
                 "    - mentions 'workflow' scope: sign in through the browser window, or give your token the 'workflow' permission\n"
                 "    - 'rejected' / 'fetch first': just run this script again")
    print("\n[ok] Done - your code is on GitHub.")


if __name__ == "__main__":
    main()
