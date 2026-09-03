#!/usr/bin/env python3
"""
Bitbucket PR poller for Shopfloor Suite.

Runs forever on your local machine. Every INTERVAL seconds it asks Bitbucket for
OPEN pull requests whose destination (target) branch is `main`. For each one it
triggers an automatic review by shelling out to:

    scripts/pr-review.sh autoreview <PR_NUMBER>

A PR is reviewed only when ALL of these hold:
    - its destination/target branch is `main` (--target) and state is OPEN;
    - it has NO comments yet (i.e. not already reviewed/commented);
    - it is at most --max-age-days old (default 4) by created_on;
    - its source branch does NOT start with `translations_`.

Seen PR ids are also persisted to a state file, so within/across restarts the
poller does not re-trigger a review for a PR it already handled this run.

Auth (same model as pr-review.py):
    export BB_EMAIL=you@schertech.com          # defaults to `git config user.email`
    export BB_TOKEN=<atlassian-api-token>      # scopes: read:repository, read:pullrequest
Alternative (Bitbucket app password):
    export BB_USER=<bitbucket-username>
    export BB_APP_PASSWORD=<app-password>

Workspace/repo are parsed from `git remote get-url origin`.

Usage:
    scripts/pr-poller.sh                       # poll every 120s, target branch main
    scripts/pr-poller.sh --interval 60         # poll every 60s
    scripts/pr-poller.sh --target develop      # watch a different target branch
    scripts/pr-poller.sh --max-age-days 7      # review PRs up to 7 days old (default 4)
    scripts/pr-poller.sh --skip-prefix wip_    # also skip PRs whose source branch starts with this
    scripts/pr-poller.sh --model opus          # override review model (default sonnet)
    scripts/pr-poller.sh --effort medium       # override review effort (default high)
    scripts/pr-poller.sh --once                # single pass then exit (cron-friendly)
    scripts/pr-poller.sh --dry-run             # log what it WOULD review, don't run the review
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

TRANSLATIONS_PREFIX = "translations_"

import requests

API = "https://api.bitbucket.org/2.0"
HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW_SH = os.path.join(HERE, "pr-review.sh")


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def die(msg):
    log(f"error: {msg}")
    sys.exit(1)


def repo_slug():
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True, cwd=HERE
        ).strip()
    except Exception:
        die("not a git repo / no origin remote")
    # git@bitbucket.org:SCT/shopfloor-suite.git  or  https://bitbucket.org/SCT/shopfloor-suite.git
    tail = url.split("bitbucket.org", 1)[-1].lstrip(":/")
    slug = tail[:-4] if tail.endswith(".git") else tail
    if slug.count("/") != 1:
        die(f"could not parse workspace/repo from remote: {url}")
    return slug


def git_email():
    try:
        return subprocess.check_output(
            ["git", "config", "user.email"], text=True, cwd=HERE
        ).strip()
    except Exception:
        return ""


def auth():
    token = os.environ.get("BB_TOKEN")
    if token:
        email = os.environ.get("BB_EMAIL") or git_email()
        if not email:
            die("BB_TOKEN set but no BB_EMAIL and no git user.email")
        return (email, token)
    user = os.environ.get("BB_USER")
    pw = os.environ.get("BB_APP_PASSWORD")
    if user and pw:
        return (user, pw)
    die("no credentials: set BB_TOKEN (+BB_EMAIL) or BB_USER+BB_APP_PASSWORD.")


def state_path():
    d = os.environ.get("PR_POLLER_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "sfs-pr-poller"
    )
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "seen.json")


def load_seen(path):
    try:
        with open(path) as f:
            return set(json.load(f).get("seen", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(path, seen):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"seen": sorted(seen)}, f, indent=2)
    os.replace(tmp, path)  # atomic


def parse_ts(s):
    """Parse a Bitbucket ISO-8601 timestamp into an aware UTC datetime."""
    if not s:
        return None
    t = s.strip().replace("Z", "+00:00")
    # Trim fractional seconds to 6 digits so datetime.fromisoformat accepts them.
    t = re.sub(r"(\.\d{6})\d+", r"\1", t)
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Client:
    def __init__(self):
        self.slug = repo_slug()
        self.s = requests.Session()
        self.s.auth = auth()

    def open_prs_for(self, target):
        """Return [(id, title, source_branch, created_on)] of OPEN PRs targeting `target`."""
        # BBQL: state=OPEN filtered to the target branch; page through results.
        q = f'state="OPEN" AND destination.branch.name="{target}"'
        url = "/".join([API, "repositories", self.slug, "pullrequests"])
        params = {"q": q, "pagelen": 50,
                  "fields": "values.id,values.title,values.source.branch.name,values.created_on,next"}
        out = []
        while url:
            r = self.s.get(url, params=params)
            if r.status_code == 401:
                die("401 unauthorized — check BB_TOKEN scopes / BB_EMAIL")
            if not r.ok:
                die(f"HTTP {r.status_code}: {r.text[:300]}")
            j = r.json()
            for pr in j.get("values", []):
                out.append((
                    pr["id"],
                    pr.get("title", ""),
                    pr.get("source", {}).get("branch", {}).get("name", "?"),
                    parse_ts(pr.get("created_on")),
                ))
            url = j.get("next")
            params = None  # `next` already carries the query
        return out

    def has_comments(self, pr_id):
        """True if the PR already has at least one non-deleted comment (i.e. reviewed/commented)."""
        url = "/".join([API, "repositories", self.slug, "pullrequests", str(pr_id), "comments"])
        r = self.s.get(url, params={"q": "deleted=false", "pagelen": 1, "fields": "values.id"})
        if r.status_code == 401:
            die("401 unauthorized — check BB_TOKEN scopes / BB_EMAIL")
        if not r.ok:
            die(f"HTTP {r.status_code} reading comments for PR #{pr_id}: {r.text[:200]}")
        return bool(r.json().get("values"))


def run_review(pr_id, args):
    cmd = [REVIEW_SH, "autoreview", str(pr_id), "--model", args.model, "--effort", args.effort]
    if args.dry_run:
        log(f"--dry-run: would run: {' '.join(cmd)}")
        return True
    if not os.access(REVIEW_SH, os.X_OK):
        die(f"{REVIEW_SH} not found or not executable (chmod +x it)")
    log(f"running: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, cwd=os.path.dirname(HERE))
    except Exception as e:
        log(f"failed to launch review for PR #{pr_id}: {e}")
        return False
    if proc.returncode != 0:
        log(f"review for PR #{pr_id} exited {proc.returncode} — will retry next poll")
        return False
    log(f"review for PR #{pr_id} done")
    return True


def poll_once(c, seen, args, now):
    prs = c.open_prs_for(args.target)
    log(f"open PRs -> {args.target}: {sorted(pr[0] for pr in prs) if prs else 'none'}")
    cutoff = now - timedelta(days=args.max_age_days)

    for pr_id, title, src, created in prs:
        # 1) already handled this run.
        if pr_id in seen:
            continue
        # 2) skip translations (or any configured) source-branch prefix.
        prefixes = tuple(p for p in [TRANSLATIONS_PREFIX, args.skip_prefix] if p)
        if src.startswith(prefixes):
            log(f"skip PR #{pr_id}: source branch '{src}' has ignored prefix")
            seen.add(pr_id)
            continue
        # 3) skip PRs older than the cutoff.
        if created is None:
            log(f"skip PR #{pr_id}: missing/unparseable created_on")
            continue
        if created < cutoff:
            age = (now - created).days
            log(f"skip PR #{pr_id}: {age}d old (> {args.max_age_days}d cutoff)")
            seen.add(pr_id)
            continue
        # 4) skip PRs that already have a comment/review.
        if c.has_comments(pr_id):
            log(f"skip PR #{pr_id}: already has comment(s)")
            seen.add(pr_id)
            continue

        # Eligible -> review.
        log(f"REVIEW PR #{pr_id}: {src} -> {args.target}  «{title}»")
        if run_review(pr_id, args):
            seen.add(pr_id)
        if not args.dry_run:
            save_seen(args.state, seen)  # persist per-PR so a crash mid-batch keeps progress

    if not args.dry_run:
        save_seen(args.state, seen)  # persist skip-marks too, so they aren't re-checked


def main():
    p = argparse.ArgumentParser(prog="pr-poller", description="Poll Bitbucket for new PRs targeting a branch and auto-review them")
    p.add_argument("--interval", type=int, default=120, help="seconds between polls (default 120)")
    p.add_argument("--target", default="main", help="target/destination branch to watch (default main)")
    p.add_argument("--max-age-days", type=int, default=4,
                   help="do not review PRs older than this many days (default 4)")
    p.add_argument("--skip-prefix", default=None,
                   help="skip PRs whose source branch starts with this (translations_ is always skipped)")
    p.add_argument("--model", default="sonnet",
                   help="model passed to autoreview (default sonnet)")
    p.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"],
                   help="reasoning effort passed to autoreview (default high)")
    p.add_argument("--once", action="store_true", help="run a single poll and exit")
    p.add_argument("--dry-run", action="store_true", help="log what would be reviewed; do not launch the review")
    p.add_argument("--state", default=None, help="path to the seen-PRs state file")
    args = p.parse_args()
    args.state = args.state or state_path()

    c = Client()
    seen = load_seen(args.state)
    log(f"repo {c.slug}  target={args.target}  interval={args.interval}s  "
        f"max-age={args.max_age_days}d  state={args.state}")
    log(f"loaded {len(seen)} previously-seen PR id(s)")

    while True:
        try:
            poll_once(c, seen, args, datetime.now(timezone.utc))
        except SystemExit:
            raise
        except Exception as e:
            log(f"poll error (continuing): {e}")
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
