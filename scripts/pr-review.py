#!/usr/bin/env python3
"""
Bitbucket PR review helper for Shopfloor Suite.

Fetches a PR's metadata + unified diff, dumps review context (diff and/or full
files with line numbers) for a human/AI reviewer, and posts findings back as
inline + summary comments on the PR.

The *review itself* (finding the issues) is done by the reviewer reading the
context this tool prints; this tool only automates fetch + post. Use the
`checklist` command to print the project convention gate the review must apply.

Auth (Atlassian API token — the model used by this repo):
    export BB_EMAIL=you@schertech.com          # defaults to `git config user.email`
    export BB_TOKEN=<atlassian-api-token-with-bitbucket-scopes>
      required scopes: read:repository:bitbucket, read:pullrequest:bitbucket,
                       write:pullrequest:bitbucket
Alternative (Bitbucket app password):
    export BB_USER=<bitbucket-username>
    export BB_APP_PASSWORD=<app-password>       # Pull requests: Write, Repositories: Read

Workspace/repo are parsed from `git remote get-url origin`.

Commands:
    autoreview <PR> [--engine cli|api] [--dry-run] [--no-dedupe] [--no-caveman] [--model M] [--files ...]
                                      FULLY AUTOMATIC: fetch -> Claude reviews against the
                                      project checklist -> post inline + summary comments.
                                      Caveman output mode is ON by default (terse review text);
                                      pass --no-caveman for full prose. On the cli engine the
                                      review is grounded in this repo's .claude/skills (sfs-map,
                                      laravel, angular, mysql, postgresql, ...).
                                      Default engine `cli` uses the local `claude` CLI (your
                                      Claude subscription — no API key). `api` uses the
                                      Anthropic API (needs ANTHROPIC_API_KEY + `anthropic` pkg).
                                      Defaults: --model sonnet, --effort high (both engines).
                                      --dry-run writes findings.json instead of posting.
    review   <PR> [--files a,b,...]   one-shot PREP: fetch + checklist + full context for a
                                      human/AI reviewer to read (does NOT post).
    fetch    <PR>                     save + summarise PR (metadata, branches, changed files)
    context  <PR> [--full] [--files a,b,...]
                                      print diff for review; --full also prints changed
                                      source files with line numbers; --files limits to a subset
    raw      <PR> <path>              print one file at the PR source commit, line-numbered
    post     <PR> <findings.json>     post summary + inline comments (see schema below)
    list     <PR>                     list existing (non-deleted) comments
    checklist                         print the project review checklist

findings.json schema:
    {
      "summary": "markdown text for a top-level PR comment (optional)",
      "findings": [
        {
          "severity": "blocker|major|minor|nit",   # -> emoji prefix
          "path":     "frontend-sap/.../foo.ts",    # dest path exactly as in the diff
          "line":     123,                          # line in the file to anchor to
          "anchor":   "to",                         # "to" (new file, default) | "from" (old file)
          "title":    "short headline (optional)",
          "body":     "full comment markdown"
        }
      ]
    }
A finding with no "path" is posted as a top-level comment.
"""
import argparse
import json
import os
import subprocess
import sys

import requests

API = "https://api.bitbucket.org/2.0"
SEV_EMOJI = {"blocker": "🔴", "major": "🟠", "minor": "🟡", "nit": "🔵"}

# CLI model aliases -> full API ids, so `--model sonnet` works for either engine.
CLI_TO_API_MODEL = {
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
    "haiku": "claude-haiku-4-5-20251001",
}


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def repo_slug():
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True
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
            ["git", "config", "user.email"], text=True
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
    die(
        "no credentials: set BB_TOKEN (+BB_EMAIL) or BB_USER+BB_APP_PASSWORD. "
        "See header of this script."
    )


class Client:
    def __init__(self):
        self.slug = repo_slug()
        self.s = requests.Session()
        self.s.auth = auth()

    def _url(self, *parts):
        return "/".join([API, "repositories", self.slug, "pullrequests", *map(str, parts)])

    def _check(self, r):
        if r.status_code == 401:
            msg = ""
            try:
                msg = r.json().get("error", {}).get("message", "")
            except Exception:
                pass
            die(f"401 unauthorized — {msg or 'check token scopes / email'}")
        if not r.ok:
            die(f"HTTP {r.status_code}: {r.text[:300]}")
        return r

    def pr(self, pr):
        return self._check(self.s.get(self._url(pr))).json()

    def diff(self, pr):
        return self._check(self.s.get(self._url(pr, "diff"))).text

    def raw_file(self, commit, path):
        url = "/".join([API, "repositories", self.slug, "src", commit, path])
        return self._check(self.s.get(url)).text

    def comments(self, pr):
        out, url = [], self._url(pr, "comments") + "?q=deleted=false&pagelen=100&sort=created_on"
        while url:
            j = self._check(self.s.get(url)).json()
            out.extend(j.get("values", []))
            url = j.get("next")
        return out

    def post_comment(self, pr, raw, path=None, line=None, anchor="to"):
        body = {"content": {"raw": raw}}
        if path and line:
            key = "from" if anchor == "from" else "to"
            body["inline"] = {"path": path, key: int(line)}
        r = self.s.post(self._url(pr, "comments"), json=body)
        self._check(r)
        return r.json()


def changed_files(diff_text):
    """Return list of (path, adds, dels) from a unified diff."""
    files, cur, adds, dels = [], None, 0, 0
    for ln in diff_text.splitlines():
        if ln.startswith("diff --git "):
            if cur:
                files.append((cur, adds, dels))
            # 'diff --git a/x b/x'
            cur = ln.split(" b/", 1)[-1]
            adds = dels = 0
        elif ln.startswith("+") and not ln.startswith("+++"):
            adds += 1
        elif ln.startswith("-") and not ln.startswith("---"):
            dels += 1
    if cur:
        files.append((cur, adds, dels))
    return files


def scratch_dir():
    d = os.environ.get("PR_REVIEW_OUT", "/tmp/pr-review")
    os.makedirs(d, exist_ok=True)
    return d


def _which(name):
    from shutil import which
    return which(name)


# --------------------------------------------------------------------------- #
CHECKLIST = """\
SHOPFLOOR SUITE — PR REVIEW CHECKLIST (apply to every finding)

GENERAL
  - No magic strings/numbers for domain values. Backend: enums in app/Enums/
    (backed/Spatie). Frontend: enums in src/app/shared/enums/. Applies to tests.
  - User-facing strings localized. FE: $localize / i18n attrs, common strings in
    shared localization + extracted to xlf. BE: keys in resources/lang/en.json
    + sibling locales (bn/de/it/pl/sk/tr) or resources/lang/en/*.php.
  - Time: store UTC everywhere (DB/API/backend). Convert to local ONLY at the FE
    display/input boundary via UtcTimeService. Never persist a local tz value.

BACKEND (Laravel 11 / PHP 8.3, PostgreSQL)
  - Thin controllers -> Services (APS logic in ApsService/ApsScheduler).
  - Models singular (AsOffer -> as_offers). New endpoints = custom REST in
    routes/api.php with controllers + API Resources. NEVER expose new data via
    OData/lodata.
  - APS (read backend/aps_context.md): full replan each run; never null
    start/end/plan_* on ops APS failed to place; MANUAL ops anchor at
    scheduleStart and don't advance the cursor; BACKWARD-pass ops pack forward;
    setup-matrix changeover gap; overdue computed via DB query.
  - Tests hit a REAL db (not mocked); run with php8.3 vendor/bin/phpunit.
  - Lint with ./vendor/bin/pint.

FRONTEND-SAP (Angular 17, NgModule, UI5, Bryntum)
  - Custom REST only via CommonService — always isLodata=false; never OData.
  - Tabular data via shared app-grid-table (global search + all-column
    server-side filter + persisted columns).
  - Models implement Deserializable; enums/interfaces in src/app/shared/.
  - Absolute path aliases (@app/@models/@enums), not relative imports.
  - Constructor DI, separate templateUrl/styleUrl, *ngIf/*ngFor (or @if/@for).

DATABASE (migrations + queries)
  - Schema changes via Laravel migrations; reversible down(); correct column
    types; index columns used in WHERE/JOIN/ORDER BY; FKs + cascade intent.
  - utf8mb4 / InnoDB (MySQL) conventions; Postgres portability gotchas.
  - No N+1 (eager load); no unbounded queries (paginate); parameter-bind — no
    string-interpolated SQL. EXPLAIN heavy queries.
  - Timestamps UTC; no local-tz defaults in DB.

SEVERITY: blocker (bug/data-loss/security) > major (wrong behavior/convention
break) > minor (quality) > nit (style). Skip pure formatting unless it changes
meaning.
"""


# --------------------------------------------------------------------------- #
def cmd_fetch(c, args):
    pr = c.pr(args.pr)
    diff = c.diff(args.pr)
    out = scratch_dir()
    with open(os.path.join(out, f"pr-{args.pr}.json"), "w") as f:
        json.dump(pr, f, indent=2)
    with open(os.path.join(out, f"pr-{args.pr}.diff"), "w") as f:
        f.write(diff)
    src = pr["source"]["branch"]["name"]
    dst = pr["destination"]["branch"]["name"]
    commit = pr["source"]["commit"]["hash"]
    print(f"PR #{args.pr}  [{pr['state']}]  {pr['title']}")
    print(f"  {src}  ->  {dst}   @ {commit[:12]}")
    print(f"  saved: {out}/pr-{args.pr}.json  {out}/pr-{args.pr}.diff")
    print("  changed files:")
    for path, a, d in changed_files(diff):
        print(f"    +{a:<4} -{d:<4} {path}")


def cmd_context(c, args):
    pr = c.pr(args.pr)
    diff = c.diff(args.pr)
    commit = pr["source"]["commit"]["hash"]
    only = set(args.files.split(",")) if args.files else None
    print(f"===== DIFF  PR #{args.pr}  {pr['title']} =====\n")
    print(diff)
    if args.full:
        print("\n===== FULL FILES (new version, line-numbered) =====")
        for path, _, _ in changed_files(diff):
            if only and path not in only:
                continue
            print(f"\n----- {path} -----")
            try:
                txt = c.raw_file(commit, path)
            except SystemExit:
                print("  (could not fetch — deleted/binary?)")
                continue
            for i, line in enumerate(txt.splitlines(), 1):
                print(f"{i:5}: {line}")


def cmd_raw(c, args):
    pr = c.pr(args.pr)
    commit = pr["source"]["commit"]["hash"]
    txt = c.raw_file(commit, args.path)
    for i, line in enumerate(txt.splitlines(), 1):
        print(f"{i:5}: {line}")


def _finding_raw(fnd):
    """Build the comment markdown from a finding (emoji + title + body)."""
    emoji = SEV_EMOJI.get(fnd.get("severity", ""), "")
    title = fnd.get("title", "")
    head = " ".join(x for x in (emoji, f"**{title}**" if title else "") if x)
    body = fnd.get("body", "")
    return (head + "\n\n" + body) if head else body


def _existing_keys(c, pr):
    """Set of (path, line, first-body-line) already commented, for dedupe."""
    keys = set()
    for cm in c.comments(pr):
        inl = cm.get("inline") or {}
        path = inl.get("path")
        line = inl.get("to") or inl.get("from")
        raw = cm.get("content", {}).get("raw", "") or ""
        first = raw.splitlines()[0].strip() if raw else ""
        keys.add((path, line, first))
    return keys


def post_findings(c, pr, data, dedupe=True):
    """Post a findings dict (summary + findings[]) to the PR. Returns count posted."""
    seen = _existing_keys(c, pr) if dedupe else set()
    posted, skipped = [], 0

    summary = data.get("summary")
    if summary:
        first = summary.splitlines()[0].strip()
        if dedupe and (None, None, first) in seen:
            skipped += 1
        else:
            j = c.post_comment(pr, summary)
            posted.append(("SUMMARY", j["id"]))
            print(f"[{j['id']}] SUMMARY")

    for fnd in data.get("findings", []):
        raw = _finding_raw(fnd)
        path = fnd.get("path")
        line = fnd.get("line")
        first = raw.splitlines()[0].strip() if raw else ""
        if dedupe and (path, line, first) in seen:
            skipped += 1
            continue
        j = c.post_comment(pr, raw, path, line, fnd.get("anchor", "to"))
        loc = f"{path.split('/')[-1]}:{line}" if path else "TOP-LEVEL"
        posted.append((loc, j["id"]))
        print(f"[{j['id']}] {loc}")

    tail = f" (skipped {skipped} duplicate(s))" if skipped else ""
    print(f"\nposted {len(posted)} comment(s) to PR #{pr}{tail}")
    return len(posted)


def cmd_post(c, args):
    with open(args.findings) as f:
        data = json.load(f)
    post_findings(c, args.pr, data, dedupe=not getattr(args, "no_dedupe", False))


def cmd_review(c, args):
    """One-shot prep: save PR, print checklist + full review context.

    Does NOT judge the code — it bundles everything a reviewer (human or AI)
    needs, then the reviewer writes findings.json and runs `post`.
    """
    cmd_fetch(c, args)
    print("\n" + "=" * 70)
    print(CHECKLIST)
    print("=" * 70)
    args.full = True
    if not hasattr(args, "files"):
        args.files = None
    cmd_context(c, args)
    print("\n" + "=" * 70)
    print(f"NEXT: write findings.json (see scripts/pr-review.findings.example.json),")
    print(f"      then:  scripts/pr-review.sh post {args.pr} findings.json")


# --------------------------------------------------------------------------- #
# Automatic review via Claude
# --------------------------------------------------------------------------- #
FINDINGS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "severity": {"type": "string", "enum": ["blocker", "major", "minor", "nit"]},
                    "path": {"type": "string"},
                    "line": {"type": "integer"},
                    "anchor": {"type": "string", "enum": ["to", "from"]},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["severity", "path", "line", "anchor", "title", "body"],
            },
        },
    },
    "required": ["summary", "findings"],
}

REVIEW_SYSTEM = (
    "You are a senior reviewer for the Shopfloor Suite MES (Laravel 11 backend, "
    "Angular 17 frontend-sap, PostgreSQL). Review the PR diff strictly against the "
    "project checklist provided. Report only real, actionable issues — correctness "
    "bugs, convention violations, security, DB/query problems. Skip pure style nits "
    "unless they change meaning. For each finding, set `path` to the destination file "
    "path exactly as in the diff, and `line` to a line that is part of the diff hunk "
    "for that file (an added/green line for anchor='to'). Prefer anchor='to'. Put a "
    "concise markdown explanation with the concrete fix in `body`. Write a short "
    "markdown `summary`. If nothing is wrong, return an empty findings array and say so "
    "in the summary. Never invent line numbers — only anchor to lines you can see in the "
    "diff/files."
)

# Caveman output mode: compress ONLY the human-readable text fields. Appended to
# the system prompt when --caveman is on (default). Deliberately explicit so it
# does NOT rely on the caveman plugin's SessionStart hook firing inside the
# headless `claude -p` subprocess (which is not guaranteed).
CAVEMAN_INSTRUCTION = (
    "\n\nCAVEMAN OUTPUT MODE — applies ONLY to the human-readable text VALUES of the "
    "`summary`, `title`, and `body` fields:\n"
    "Write those values terse, like a smart caveman. Drop articles (a/an/the), filler "
    "(just/really/basically/simply), pleasantries, and hedging. Fragments OK. Short "
    "synonyms (big not extensive, fix not 'implement a solution for'). Keep ALL technical "
    "substance, file paths, symbol/function names, code snippets, and error strings EXACT "
    "and unabbreviated.\n"
    "DO NOT caveman-ify the JSON itself: keys, quoting, and the `severity`/`path`/`line`/"
    "`anchor` values stay verbatim, and fenced code blocks stay unchanged. Output must "
    "remain valid JSON matching the schema."
)

# Appended ONLY on the local `claude` CLI engine, where this repo's project skills
# (.claude/skills) auto-resolve. Tells the reviewer to ground findings in the real
# project conventions + error catalogs the skills encode. Meaningless on the API
# engine (no skill resolution there), so it is added only for the CLI path.
SKILLS_INSTRUCTION = (
    "\n\nPROJECT SKILLS — this repo ships skills in .claude/skills that encode the real "
    "Shopfloor Suite conventions and error catalogs. Use them to ground the review:\n"
    "  - sfs-map: where things live (orient before judging)\n"
    "  - laravel: backend conventions + Laravel/PHP/SQLSTATE error catalog\n"
    "  - angular: frontend-sap conventions + Angular/TypeScript error catalog\n"
    "  - mysql / postgresql: DB conventions + SQLSTATE error catalogs\n"
    "  - graphify: codebase knowledge graph (what-calls-X / trace-Y) if graphify-out/ exists\n"
    "  - caveman-review: one-line comment style (location, problem, fix)\n"
    "Invoke a skill with /<skill-name> (e.g. /laravel) when it helps judge a change, and "
    "apply their conventions to every finding."
)

# Appended when driving the `claude` CLI, which has no structured-output mode.
JSON_ONLY = (
    "\n\nReturn ONLY a single JSON object, no prose, no markdown fences. Shape:\n"
    '{"summary": "<markdown>", "findings": [{"severity": "blocker|major|minor|nit", '
    '"path": "<dest path>", "line": <int>, "anchor": "to", "title": "<short>", '
    '"body": "<markdown fix>"}]}'
)


def _extract_findings(text):
    """Parse a findings dict from model text (tolerates ``` fences / stray prose)."""
    t = text.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1 or j < i:
        die(f"model did not return JSON:\n{t[:500]}")
    return json.loads(t[i : j + 1])


def _review_via_cli(prompt, model, effort, system=REVIEW_SYSTEM):
    """Run the review through the local `claude` CLI (uses your Claude subscription)."""
    claude_bin = _which("claude")
    if not claude_bin:
        die("`claude` CLI not found — install Claude Code, or use --engine api")
    # Use the resolved path, not the bare name: on Windows `claude` is an npm
    # .cmd shim, and subprocess.run() (no shell=True) needs the exact filename
    # with extension — CreateProcess doesn't do PATHEXT resolution like a shell.
    cmd = [claude_bin, "-p", "--output-format", "json", "--system-prompt", system]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    print(f"reviewing via claude CLI (subscription)"
          f"{f', model={model}' if model else ''}{f', effort={effort}' if effort else ''}...",
          file=sys.stderr)
    # encoding="utf-8" is required explicitly: text=True alone falls back to
    # locale.getpreferredencoding() for the subprocess pipes, which on Windows
    # is the console codepage (e.g. cp1252) — that can't encode arbitrary
    # UTF-8 content (PR diffs/descriptions routinely contain smart quotes,
    # em dashes, etc.) and crashes with UnicodeEncodeError writing to stdin.
    proc = subprocess.run(
        cmd, input=prompt + JSON_ONLY, capture_output=True, text=True, encoding="utf-8", timeout=1800
    )
    if proc.returncode != 0:
        die(f"claude CLI failed (exit {proc.returncode}): {proc.stderr.strip()[:400]}")
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        die(f"claude CLI returned non-JSON envelope:\n{proc.stdout[:400]}")
    if env.get("is_error"):
        die(f"claude CLI error: {env.get('result', '')[:400]}")
    return _extract_findings(env.get("result", ""))


def _review_via_api(prompt, model, effort, system=REVIEW_SYSTEM):
    """Run the review through the Anthropic API (needs ANTHROPIC_API_KEY + anthropic pkg)."""
    try:
        import anthropic
    except ImportError:
        die("--engine api needs the anthropic package: pip install anthropic")
    model = CLI_TO_API_MODEL.get(model, model)  # allow `--model sonnet` on the API engine
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY or an `ant auth login` profile
    print(f"reviewing via Anthropic API ({model}, effort={effort})...", file=sys.stderr)
    with client.messages.stream(
        model=model,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": FINDINGS_SCHEMA}},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        die("Claude refused to review this content")
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    return _extract_findings(text)


def cmd_autoreview(c, args):
    pr = c.pr(args.pr)
    diff = c.diff(args.pr)
    commit = pr["source"]["commit"]["hash"]
    only = set(args.files.split(",")) if args.files else None

    # Build line-numbered file context so the model can anchor accurately.
    files_ctx = []
    for path, _, _ in changed_files(diff):
        if only and path not in only:
            continue
        try:
            txt = c.raw_file(commit, path)
        except SystemExit:
            continue
        numbered = "\n".join(f"{i:5}: {ln}" for i, ln in enumerate(txt.splitlines(), 1))
        files_ctx.append(f"----- {path} (new version, line-numbered) -----\n{numbered}")

    prompt = (
        f"{CHECKLIST}\n\n"
        f"===== PR #{args.pr}: {pr['title']} =====\n"
        f"Source {pr['source']['branch']['name']} -> {pr['destination']['branch']['name']}\n\n"
        f"===== UNIFIED DIFF =====\n{diff}\n\n"
        f"===== CHANGED FILES (for accurate line numbers) =====\n"
        + "\n\n".join(files_ctx)
        + "\n\nReview this PR now."
    )

    # Caveman output mode on by default (compresses only the text fields). --no-caveman opts out.
    caveman = not getattr(args, "no_caveman", False)
    system = REVIEW_SYSTEM + (CAVEMAN_INSTRUCTION if caveman else "")
    if caveman:
        print("caveman output mode ON (terse review text; --no-caveman to disable)", file=sys.stderr)

    if args.engine == "api":
        data = _review_via_api(prompt, args.model or "claude-sonnet-5", args.effort, system)
    else:
        system += SKILLS_INSTRUCTION  # project skills resolve only in the local CLI
        print("using project skills from .claude/skills (sfs-map/laravel/angular/mysql/postgresql/...)",
              file=sys.stderr)
        data = _review_via_cli(prompt, args.model, args.effort, system)

    n = len(data.get("findings", []))
    print(f"Claude produced {n} finding(s).", file=sys.stderr)

    if args.dry_run:
        out = os.path.join(scratch_dir(), f"pr-{args.pr}.findings.json")
        with open(out, "w") as f:
            json.dump(data, f, indent=2)
        print(f"--dry-run: wrote {out} (not posted). Review it, then:")
        print(f"  scripts/pr-review.sh post {args.pr} {out}")
        return

    post_findings(c, args.pr, data, dedupe=not args.no_dedupe)


def cmd_list(c, args):
    for cm in c.comments(args.pr):
        inl = cm.get("inline")
        loc = f"{inl['path'].split('/')[-1]}:{inl.get('to') or inl.get('from')}" if inl else "TOP-LEVEL"
        who = cm["user"]["display_name"]
        first = cm["content"]["raw"].splitlines()[0][:70] if cm["content"]["raw"] else ""
        print(f"  id={cm['id']} [{loc}] {who}: {first}")


def cmd_checklist(c, args):
    print(CHECKLIST)


def main():
    p = argparse.ArgumentParser(prog="pr-review", description="Bitbucket PR review helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch"); s.add_argument("pr"); s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("context"); s.add_argument("pr")
    s.add_argument("--full", action="store_true"); s.add_argument("--files")
    s.set_defaults(fn=cmd_context)
    s = sub.add_parser("raw"); s.add_argument("pr"); s.add_argument("path"); s.set_defaults(fn=cmd_raw)
    s = sub.add_parser("post"); s.add_argument("pr"); s.add_argument("findings")
    s.add_argument("--no-dedupe", action="store_true"); s.set_defaults(fn=cmd_post)
    s = sub.add_parser("review"); s.add_argument("pr")
    s.add_argument("--files"); s.set_defaults(fn=cmd_review)
    s = sub.add_parser("autoreview"); s.add_argument("pr")
    s.add_argument("--engine", default="cli", choices=["cli", "api"],
                   help="cli = local `claude` (your subscription, default); api = Anthropic API key")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--no-dedupe", action="store_true")
    s.add_argument("--model", default="sonnet",
                   help="cli: opus/sonnet/etc (default sonnet); api: full id or alias (default claude-sonnet-5)")
    s.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"],
                   help="reasoning effort for both engines (default high)")
    s.add_argument("--no-caveman", action="store_true",
                   help="disable caveman output mode (on by default: terse summary/title/body text)")
    s.add_argument("--files"); s.set_defaults(fn=cmd_autoreview)
    s = sub.add_parser("list"); s.add_argument("pr"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("checklist"); s.set_defaults(fn=cmd_checklist)

    args = p.parse_args()
    # checklist needs no network/auth
    client = None if args.cmd == "checklist" else Client()
    args.fn(client, args)


if __name__ == "__main__":
    main()
