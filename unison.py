#!/usr/bin/env python3
"""Unison: a tiny local work tracker.

Tasks you write down + Claude Code sessions + git commits, grouped into
buckets (Forte, Uni, ArqaMed, ZAP, ...). Standard library only.

  unison serve                  run the dashboard + background scanner
  unison scan                   scan sessions and commits once
  unison add <text> [--cwd D]   add a task  (@bucket  !due fri 18:00  * = pin)
  unison ls [--all]             list open tasks
  unison done|pin|doing|rm <id>
  unison summary [day] [bucket] Claude-written summary (day: yesterday, mon, 21.10, ...)
  unison hook-session-start     Claude Code SessionStart hook (reads JSON on stdin)
"""
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB_PATH = DATA / "unison.db"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
HOME = str(Path.home())


def load_config():
    cfg = json.loads((ROOT / "config.json").read_text())
    for b in cfg["buckets"]:
        b["paths"] = [os.path.expanduser(p).rstrip("/") for p in b.get("paths", [])]
        b["repos"] = [r.lower() for r in b.get("repos", [])]
    cfg["repo_roots"] = [os.path.expanduser(p) for p in cfg["repo_roots"]]
    cfg["author_emails"] = {e.lower() for e in cfg.get("author_emails", [])}
    return cfg


CFG = load_config()
BUCKETS = {b["id"]: b for b in CFG["buckets"]}
SCAN_LOCK = threading.Lock()
SUMMARY_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, bucket TEXT NOT NULL,
  due TEXT, pinned INTEGER DEFAULT 0, status TEXT DEFAULT 'todo',
  created REAL, updated REAL, done_at REAL);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, bucket TEXT, project TEXT, cwd TEXT, title TEXT,
  first_prompt TEXT, recap TEXT, start REAL, end REAL, active_min REAL,
  prompts INTEGER, cost REAL);
CREATE TABLE IF NOT EXISTS session_days (
  session_id TEXT, day TEXT, minutes REAL, PRIMARY KEY (session_id, day));
CREATE TABLE IF NOT EXISTS commits (
  hash TEXT PRIMARY KEY, bucket TEXT, project TEXT, repo TEXT, ts REAL, subject TEXT);
CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime REAL, size INTEGER);
CREATE TABLE IF NOT EXISTS notified (task_id INTEGER, day TEXT, PRIMARY KEY (task_id, day));
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS summaries (
  day TEXT, bucket TEXT, text TEXT, created REAL, fp TEXT, PRIMARY KEY (day, bucket));
CREATE INDEX IF NOT EXISTS idx_sd_day ON session_days(day);
CREATE INDEX IF NOT EXISTS idx_commits_ts ON commits(ts);
CREATE INDEX IF NOT EXISTS idx_sessions_end ON sessions(end);
"""


SCHEMA_VERSION = 2
MIGRATIONS = [
    ("sessions", "git_cmds", "TEXT"),      # text of `git commit` commands the session ran
    ("sessions", "git_hashes", "TEXT"),    # hex tokens seen in the session's git output
    ("commits", "session_id", "TEXT"),
    ("commits", "link", "TEXT"),           # 'claude' = made in the session, 'time' = during it
]


def db():
    DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    for table, col, typ in MIGRATIONS:
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    v = con.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
    if not v or int(v[0]) < SCHEMA_VERSION:
        con.execute("DELETE FROM files")  # force a re-parse of transcripts
        con.execute("INSERT OR REPLACE INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
    con.commit()
    return con


# ---------------------------------------------------------------- buckets

_repo_cache = {}


def find_repo(path):
    """Return (repo_dir, origin_url) for the git repo containing path."""
    p = Path(path)
    for cand in [p, *p.parents]:
        if str(cand) in _repo_cache:
            return _repo_cache[str(cand)]
        if (cand / ".git").exists():
            try:
                url = subprocess.run(
                    ["git", "-C", str(cand), "remote", "get-url", "origin"],
                    capture_output=True, text=True, timeout=5).stdout.strip()
            except Exception:
                url = ""
            _repo_cache[str(cand)] = (str(cand), url)
            return _repo_cache[str(cand)]
        if str(cand) in (HOME, "/"):
            break
    return (None, "")


def remote_slug(url):
    """'https://github.com/Owner/Repo.git' -> 'Owner/Repo' (also ssh and other hosts)."""
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$", url or "")
    return m.group(1) if m else ""


def classify(path):
    """Map a directory to (bucket_id, project_name).

    1. GitHub remote matches a bucket's 'repos' rule  -> that bucket, project = repo name
    2. folder is under a bucket's 'paths'             -> that bucket
    3. otherwise                                      -> default bucket
    """
    path = os.path.abspath(os.path.expanduser(path or HOME)).rstrip("/")
    repo, url = find_repo(path)
    slug = remote_slug(url)

    bucket = None
    if slug:
        for b in CFG["buckets"]:
            if any(fnmatch.fnmatchcase(slug.lower(), r) for r in b["repos"]):
                bucket = b["id"]
                break
    best_root, path_bucket = None, None
    for b in CFG["buckets"]:
        for p in b["paths"]:
            if (path == p or path.startswith(p + "/")) and (best_root is None or len(p) > len(best_root)):
                best_root, path_bucket = p, b["id"]
    bucket = bucket or path_bucket or CFG["default_bucket"]

    if slug:
        project = slug.split("/")[1]          # worktrees/clones of one repo share a name
    elif repo:
        project = os.path.basename(repo)
    elif best_root and path != best_root:
        project = path[len(best_root) + 1:].split("/")[0]
    else:
        project = os.path.basename(path) or "~"
    return bucket, project


def resolve_bucket(name, prefix=False):
    n = name.lower()
    for b in CFG["buckets"]:
        if n == b["id"] or n == b["name"].lower() or n in b.get("aliases", []):
            return b["id"]
    if prefix and n:
        hits = {b["id"] for b in CFG["buckets"]
                if any(w.startswith(n) for w in [b["id"], b["name"].lower(), *b.get("aliases", [])])}
        if len(hits) == 1:
            return hits.pop()
    return None


# ---------------------------------------------------------------- task text parsing

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _future(d, today):
    return d if d >= today else d.replace(year=d.year + 1)


def parse_due(tok, today=None):
    today = today or date.today()
    t = tok.lower().strip()
    try:
        if t in ("today", "tod", "td"):
            return today
        if t in ("tomorrow", "tmr", "tom", "tm"):
            return today + timedelta(days=1)
        if t in ("nextweek", "nw"):
            return today + timedelta(days=7 - today.weekday())
        if t[:3] in WEEKDAYS and (len(t) == 3 or t.startswith(t[:3]) and t.endswith("day")):
            return today + timedelta(days=(WEEKDAYS.index(t[:3]) - today.weekday()) % 7)
        m = re.fullmatch(r"\+(\d+)([dw]?)", t)
        if m:
            n = int(m.group(1)) * (7 if m.group(2) == "w" else 1)
            return today + timedelta(days=n)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
            return date.fromisoformat(t)
        m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", t)
        if m:
            y = int(m.group(3)) if m.group(3) else today.year
            y = y + 2000 if y < 100 else y
            d = date(y, int(m.group(2)), int(m.group(1)))
            return d if m.group(3) else _future(d, today)
        m = re.fullmatch(r"(\d{1,2})([a-z]{3})[a-z]*|([a-z]{3})[a-z]*(\d{1,2})", t)
        if m:
            day = int(m.group(1) or m.group(4))
            mon = (m.group(2) or m.group(3))
            if mon in MONTHS:
                return _future(date(today.year, MONTHS.index(mon) + 1, day), today)
    except ValueError:
        return None
    return None


def parse_time(tok):
    """'18:00', '9:30', '18h', '6pm', '6:30pm' -> 'HH:MM' (a bare number is not a time)."""
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm|h)?", tok.lower().strip())
    if not m or (m.group(2) is None and m.group(3) is None):
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) == "pm" and h < 12:
        h += 12
    if m.group(3) == "am" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def parse_when(expr, today=None):
    """'today', 'fri', 'fri@14:00', '18:00' -> (date | None, 'HH:MM' | None)."""
    today = today or date.today()
    if "@" in expr:
        d, t = expr.split("@", 1)
        d, t = parse_due(d, today), parse_time(t)
        return (d, t) if d and t else (None, None)
    t = parse_time(expr)
    if t:  # time only: today, or tomorrow if that time has passed
        d = today if t > datetime.now().strftime("%H:%M") or today != date.today() else today + timedelta(days=1)
        return d, t
    return parse_due(expr, today), None


def fmt_due(d, t):
    return (d.isoformat() + (f"T{t}" if t else "")) if d else None


def parse_task_text(text, default_bucket=None):
    """Task grammar: free text plus
         @bucket | #bucket        bucket (unique prefix ok: @arq)
         !today  !fri  !30.10     deadline        !due <date> [time]  also works
         !fri@14:00  !18:00       deadline with time; a time may also follow the date: !today 18:00
         *                        pin
    """
    toks = text.split()
    title, bucket, due_d, due_t, pinned = [], None, None, None, False
    i = 0
    while i < len(toks):
        tok, low = toks[i], toks[i].lower()
        if tok[:1] in "@#" and len(tok) > 1 and resolve_bucket(tok[1:], prefix=True):
            bucket = resolve_bucket(tok[1:], prefix=True)
        elif tok in ("*", "!pin", "📌"):
            pinned = True
        elif low.startswith("!") and len(low) > 1:
            expr = low[1:]
            if expr == "due":
                nxt = toks[i + 1].lower() if i + 1 < len(toks) else ""
                if nxt and any(parse_when(nxt)):
                    i += 1
                    expr = nxt
                else:
                    i += 1
                    continue
            d, t = parse_when(expr)
            if d is None:
                title.append(tok)
            else:
                due_d, due_t = d, t
                if t is None and i + 1 < len(toks) and parse_time(toks[i + 1]):
                    due_t = parse_time(toks[i + 1])
                    i += 1
        else:
            title.append(tok)
        i += 1
    return {
        "title": " ".join(title).strip(),
        "bucket": bucket or default_bucket or CFG["default_bucket"],
        "due": fmt_due(due_d, due_t),
        "pinned": pinned,
    }


def due_parts(due):
    """'2026-10-23T18:00' -> (date, '18:00'); '2026-10-23' -> (date, None)."""
    return date.fromisoformat(due[:10]), (due[11:16] or None)


def due_dt(due):
    d, t = due_parts(due)
    return datetime.combine(d, datetime.strptime(t or "23:59", "%H:%M").time())


# ---------------------------------------------------------------- tasks

def add_task(con, title, bucket, due=None, pinned=False):
    now = time.time()
    cur = con.execute(
        "INSERT INTO tasks (title, bucket, due, pinned, status, created, updated) VALUES (?,?,?,?,?,?,?)",
        (title, bucket, due, int(bool(pinned)), "todo", now, now))
    con.commit()
    return cur.lastrowid


def update_task(con, tid, fields):
    if "due_text" in fields:  # free-form: 'fri 18:00', 'tmr', '' to clear
        txt = (fields.pop("due_text") or "").strip()
        fields["due"] = parse_task_text("x !due " + txt)["due"] if txt else None
        if txt and not fields["due"]:
            raise ValueError(f"can't read date: {txt}")
    allowed = {"title", "bucket", "due", "pinned", "status"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "status":
            if v not in ("todo", "doing", "done"):
                continue
            sets.append("done_at=?")
            vals.append(time.time() if v == "done" else None)
        if k == "pinned":
            v = int(bool(v))
        if k == "bucket" and v not in BUCKETS:
            continue
        if k == "due" and v:
            d, t = due_parts(v)
            if t:
                datetime.strptime(t, "%H:%M")
            v = fmt_due(d, t)
        sets.append(f"{k}=?")
        vals.append(v or None if k == "due" else v)
    if not sets:
        return
    sets.append("updated=?")
    vals.append(time.time())
    con.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", (*vals, tid))
    con.commit()


def task_rows(con, include_done_days=7):
    cutoff = time.time() - include_done_days * 86400
    rows = con.execute(
        "SELECT * FROM tasks WHERE status!='done' OR done_at>=? ORDER BY id", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- scanning: Claude sessions

TS_RE = re.compile(rb'"timestamp":"([^"]+)"')
TYPE_RE = re.compile(rb'"type":"(user|assistant)"')
HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


def parse_ts(s):
    if isinstance(s, bytes):
        s = s.decode()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def prompt_text(msg):
    """Extract a human-typed prompt from a user message, or None."""
    content = msg.get("content")
    if isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return None
        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    if not isinstance(content, str):
        return None
    text = content.strip()
    m = re.match(r"<command-name>/?([^<]+)</command-name>", text) or \
        re.search(r"<command-name>/?([^<]+)</command-name>", text)
    if m:
        args = re.search(r"<command-args>([^<]*)</command-args>", text)
        return ("/" + m.group(1).strip() + (" " + args.group(1).strip() if args and args.group(1).strip() else ""))
    if text.startswith("<") or text.startswith("Caveat:"):
        return None
    text = re.sub(r"\[Image #\d+\]", "", text).strip()
    return text or None


def parse_session(path):
    s = {"id": path.stem, "cwd": None, "title": None, "recap": None, "first_prompt": None,
         "cost": None, "prompts": 0}
    stamps = []
    git_ids, git_cmds, git_hashes = set(), [], set()
    with open(path, "rb") as fh:
        for raw in fh:
            if len(raw) > 300_000:  # huge line (images / big tool output): cheap path
                if b'"isSidechain":true' in raw[:3000]:
                    continue
                if TYPE_RE.search(raw[:3000]):
                    m = TS_RE.search(raw)
                    if m and (t := parse_ts(m.group(1))):
                        stamps.append(t)
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            typ = d.get("type")
            if typ == "ai-title":
                s["title"] = d.get("aiTitle") or s["title"]
            elif typ == "cost-state":
                s["cost"] = d.get("totalCostUSD")
            elif typ == "system" and d.get("subtype") == "away_summary":
                rc = d.get("content")
                if isinstance(rc, str):
                    s["recap"] = re.sub(r"\s*\(disable recaps in /config\)\s*$", "", rc).strip()
            elif typ in ("user", "assistant"):
                if d.get("isSidechain"):
                    continue
                t = parse_ts(d.get("timestamp", ""))
                if t:
                    stamps.append(t)
                s["cwd"] = s["cwd"] or d.get("cwd")
                msg = d.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                    for c in msg["content"]:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") == "tool_use":
                            cmd = (c.get("input") or {}).get("command")
                            if isinstance(cmd, str) and "git " in cmd:
                                git_ids.add(c.get("id"))
                                if "commit" in cmd:
                                    git_cmds.append(cmd[:4000])
                        elif c.get("type") == "tool_result" and c.get("tool_use_id") in git_ids:
                            out = c.get("content")
                            out = out if isinstance(out, str) else json.dumps(out)
                            git_hashes.update(HEX_RE.findall(out))
                if typ == "user" and not d.get("isMeta") and isinstance(d.get("message"), dict):
                    txt = prompt_text(d["message"])
                    if txt:
                        s["prompts"] += 1
                        if not s["first_prompt"]:
                            s["first_prompt"] = txt[:300]
    if not stamps or not s["cwd"]:
        return None
    stamps.sort()
    gap = CFG["idle_gap_minutes"] * 60
    days = {}
    prev = None
    for t in stamps:
        add = 60.0 if prev is None or t - prev > gap else t - prev  # a new burst counts 1 min
        day = datetime.fromtimestamp(t).date().isoformat()
        days[day] = days.get(day, 0) + add / 60
        prev = t
    s["start"], s["end"] = stamps[0], stamps[-1]
    s["git_cmds"] = "\n\x1e\n".join(git_cmds)
    s["git_hashes"] = " ".join(sorted(h[:7] for h in git_hashes))
    s["days"] = days
    s["active_min"] = sum(days.values())
    return s


def scan_sessions(con):
    cutoff = time.time() - CFG["history_days"] * 86400
    changed = 0
    for f in CLAUDE_PROJECTS.glob("*/*.jsonl"):
        try:
            st = f.stat()
        except FileNotFoundError:
            continue
        row = con.execute("SELECT mtime, size FROM files WHERE path=?", (str(f),)).fetchone()
        if row and row["mtime"] == st.st_mtime and row["size"] == st.st_size:
            continue
        if st.st_mtime >= cutoff:
            s = parse_session(f)
            if s:
                bucket, project = classify(s["cwd"])
                con.execute(
                    "INSERT OR REPLACE INTO sessions (id, bucket, project, cwd, title, first_prompt, recap,"
                    " start, end, active_min, prompts, cost, git_cmds, git_hashes)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (s["id"], bucket, project, s["cwd"], s["title"], s["first_prompt"], s["recap"],
                     s["start"], s["end"], s["active_min"], s["prompts"], s["cost"],
                     s["git_cmds"], s["git_hashes"]))
                con.execute("DELETE FROM session_days WHERE session_id=?", (s["id"],))
                con.executemany("INSERT INTO session_days VALUES (?,?,?)",
                                [(s["id"], d, m) for d, m in s["days"].items()])
                changed += 1
        con.execute("INSERT OR REPLACE INTO files VALUES (?,?,?)", (str(f), st.st_mtime, st.st_size))
        con.commit()
    return changed


# ---------------------------------------------------------------- scanning: git

SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", "dist", "build", "site-packages"}


def find_repos(max_depth=3):
    repos = []

    def walk(d, depth):
        if (d / ".git").exists():
            repos.append(d)
            return
        if depth >= max_depth:
            return
        try:
            for c in sorted(d.iterdir()):
                if c.is_dir() and not c.is_symlink() and not c.name.startswith(".") and c.name not in SKIP_DIRS:
                    walk(c, depth + 1)
        except (PermissionError, OSError):
            pass

    for root in CFG["repo_roots"]:
        if Path(root).is_dir():
            walk(Path(root), 0)
    return repos


def reclassify(con):
    """Re-apply bucket rules to stored sessions/commits (cheap; picks up config edits)."""
    for (cwd,) in con.execute("SELECT DISTINCT cwd FROM sessions").fetchall():
        con.execute("UPDATE sessions SET bucket=?, project=? WHERE cwd=?", (*classify(cwd), cwd))
    for (repo,) in con.execute("SELECT DISTINCT repo FROM commits").fetchall():
        con.execute("UPDATE commits SET bucket=?, project=? WHERE repo=?", (*classify(repo), repo))
    con.commit()


def scan_commits(con):
    since = f"{CFG['history_days']} days ago"
    added = 0
    for repo in find_repos():
        emails = set(CFG["author_emails"])
        try:
            local = subprocess.run(["git", "-C", str(repo), "config", "user.email"],
                                   capture_output=True, text=True, timeout=5).stdout.strip().lower()
            if local:
                emails.add(local)
            out = subprocess.run(
                ["git", "-C", str(repo), "log", "--all", "--no-merges", f"--since={since}",
                 "--format=%H%x1f%at%x1f%ae%x1f%s"],
                capture_output=True, text=True, timeout=30).stdout
        except Exception:
            continue
        bucket, project = classify(str(repo))
        rows = []
        for line in out.splitlines():
            parts = line.split("\x1f", 3)
            if len(parts) == 4 and parts[2].lower() in emails:
                rows.append((parts[0], bucket, project, str(repo), float(parts[1]), parts[3][:300]))
        before = con.total_changes
        con.executemany("INSERT OR IGNORE INTO commits (hash, bucket, project, repo, ts, subject)"
                        " VALUES (?,?,?,?,?,?)", rows)
        added += con.total_changes - before
    con.commit()
    return added


def link_commits(con):
    """Attach each commit to the Claude session it most likely came from.

    'claude': the commit's subject appears in a `git commit` the session ran, or its
              hash showed up in the session's git output while the session was active.
    'time'  : same project, committed while the session was open (or shortly after).
    """
    before, after = 5 * 60, 30 * 60
    sessions = {}
    for r in con.execute("SELECT id, project, start, end, git_cmds, git_hashes FROM sessions"):
        sessions.setdefault(r["project"], []).append(dict(r))
    updates = []
    for c in con.execute("SELECT hash, project, ts, subject FROM commits").fetchall():
        best, best_rank = None, None
        subj = (c["subject"] or "").strip()
        for s in sessions.get(c["project"], []):
            in_window = s["start"] - before <= c["ts"] <= s["end"] + after
            near = s["start"] - 86400 <= c["ts"] <= s["end"] + 86400
            made = (near and len(subj) >= 10 and subj in (s["git_cmds"] or "")) or \
                   (in_window and c["hash"][:7] in (s["git_hashes"] or "").split())
            if not (made or in_window):
                continue
            inside = s["start"] <= c["ts"] <= s["end"]
            # prefer: made by Claude > commit inside the session > closest session end
            rank = (0 if made else 1, 0 if inside else 1, abs(c["ts"] - s["end"]))
            if best_rank is None or rank < best_rank:
                best, best_rank = s, rank
        if best:
            updates.append((best["id"], "claude" if best_rank[0] == 0 else "time", c["hash"]))
        else:
            updates.append((None, None, c["hash"]))
    con.executemany("UPDATE commits SET session_id=?, link=? WHERE hash=?", updates)
    con.commit()


def scan():
    with SCAN_LOCK:
        con = db()
        try:
            _repo_cache.clear()
            s = scan_sessions(con)
            c = scan_commits(con)
            reclassify(con)
            link_commits(con)
            con.execute("INSERT OR REPLACE INTO meta VALUES ('scanned_at', ?)", (str(time.time()),))
            con.commit()
            return {"sessions": s, "commits": c}
        finally:
            con.close()


# ---------------------------------------------------------------- reminders

def send_notification(title, body):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Unison", "-i", "appointment-soon", title, body],
                       capture_output=True, timeout=10)
    topic = CFG.get("notify", {}).get("ntfy_topic")
    if topic:
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                         headers={"Title": title})
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass


def check_reminders():
    """Morning digest of overdue/today/tomorrow tasks, plus a heads-up before timed deadlines."""
    n = CFG.get("notify", {})
    if not n.get("enabled", True):
        return
    now, today = datetime.now(), date.today()
    bname = lambda r: BUCKETS.get(r["bucket"], {}).get("name", r["bucket"])
    con = db()
    try:
        # 1) timed tasks due within the lead time (once per task per deadline)
        lead = timedelta(minutes=n.get("lead_minutes", 60))
        for r in con.execute("SELECT * FROM tasks WHERE status!='done' AND due LIKE '%T%'").fetchall():
            key = "soon:" + r["due"]
            if now <= due_dt(r["due"]) <= now + lead and not con.execute(
                    "SELECT 1 FROM notified WHERE task_id=? AND day=?", (r["id"], key)).fetchone():
                mins = max(1, round((due_dt(r["due"]) - now).total_seconds() / 60))
                send_notification(f"Due in {mins} min: {r['title']}", f"{bname(r)} · {r['due'][11:16]}")
                con.execute("INSERT OR IGNORE INTO notified VALUES (?,?)", (r["id"], key))
        con.commit()

        # 2) morning digest
        if now.hour < n.get("hour", 9):
            return
        rows = con.execute(
            "SELECT * FROM tasks WHERE status!='done' AND due IS NOT NULL AND substr(due,1,10)<=? "
            "AND id NOT IN (SELECT task_id FROM notified WHERE day=?) ORDER BY due",
            ((today + timedelta(days=1)).isoformat(), today.isoformat())).fetchall()
        if not rows:
            return
        lines = []
        for r in rows:
            d, t = due_parts(r["due"])
            when = "overdue" if due_dt(r["due"]) < now else "today" if d == today else "tomorrow"
            lines.append(f"• {r['title']} ({bname(r)}, {when}{' ' + t if t else ''})")
        send_notification(f"{len(rows)} task{'s' if len(rows) > 1 else ''} due", "\n".join(lines))
        con.executemany("INSERT OR IGNORE INTO notified VALUES (?,?)",
                        [(r["id"], today.isoformat()) for r in rows])
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------- daily summaries

SUMMARY_SYSTEM = (
    "You write a person's private daily work log. You get raw activity for one work area on one day: "
    "Claude Code sessions (title, first prompt, the assistant's recap, minutes) and git commits. "
    "Write 2-4 terse bullet lines (never more than 4, each under 30 words) starting with '- ' saying what actually got done or decided, concrete "
    "(features, fixes, investigations, decisions), merging duplicates and skipping noise. Name the project "
    "when there is more than one. If something is clearly left open, end with one line 'Next: ...'. "
    "Plain text, no headings, no preamble, no praise, no time totals. Write in {lang}."
)


def day_bounds(day):
    start = datetime.combine(date.fromisoformat(day), datetime.min.time()).timestamp()
    return start, start + 86400


def gather_day(con, day, bucket):
    """Plain-text activity digest for one bucket on one day ('' if nothing happened)."""
    t0, t1 = day_bounds(day)
    lines = []
    sessions = con.execute(
        "SELECT s.*, sd.minutes day_min FROM session_days sd JOIN sessions s ON s.id=sd.session_id "
        "WHERE sd.day=? AND s.bucket=? AND sd.minutes>=2 ORDER BY s.start", (day, bucket)).fetchall()
    for s in sessions:
        lines.append(f"SESSION [{s['project']}] {round(s['day_min'])} min: {s['title'] or ''}")
        if s["first_prompt"]:
            lines.append(f"  first prompt: {s['first_prompt'][:300]}")
        if s["recap"]:
            lines.append(f"  recap: {s['recap'][:600]}")
        for c in con.execute("SELECT subject FROM commits WHERE session_id=? AND ts>=? AND ts<? ORDER BY ts",
                             (s["id"], t0, t1)):
            lines.append(f"  commit: {c['subject']}")
    for c in con.execute(
            "SELECT project, subject FROM commits WHERE bucket=? AND ts>=? AND ts<? AND "
            "(session_id IS NULL OR session_id NOT IN (SELECT session_id FROM session_days WHERE day=?)) ORDER BY ts",
            (bucket, t0, t1, day)):
        lines.append(f"COMMIT [{c['project']}] {c['subject']}")
    for t in con.execute("SELECT title FROM tasks WHERE bucket=? AND status='done' AND done_at>=? AND done_at<?",
                         (bucket, t0, t1)):
        lines.append(f"TASK DONE: {t['title']}")
    return "\n".join(lines)


def run_claude(system, prompt):
    cfg = CFG.get("summary", {})
    exe = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")
    r = subprocess.run(
        [exe, "-p", "--model", cfg.get("model", "haiku"), "--no-session-persistence", "--tools", "",
         "--setting-sources", "", "--strict-mcp-config", "--no-chrome", "--system-prompt", system],
        input=prompt, capture_output=True, text=True, timeout=180, cwd=str(DATA))
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r.stdout.strip()


def summarize(day, bucket, force=False):
    """Create/refresh the summary for (day, bucket). Returns text, or None if no activity."""
    con = db()
    try:
        digest = gather_day(con, day, bucket)
        if not digest:
            return None
        fp = hashlib.sha1(digest.encode()).hexdigest()
        row = con.execute("SELECT text, fp FROM summaries WHERE day=? AND bucket=?", (day, bucket)).fetchone()
        if row and row["fp"] == fp and not force:
            return row["text"]
    finally:
        con.close()
    name = BUCKETS[bucket]["name"]
    nice_day = date.fromisoformat(day).strftime("%A %d %B %Y")
    text = run_claude(SUMMARY_SYSTEM.format(lang=CFG.get("summary", {}).get("language", "English")),
                      f"Work area: {name}\nDay: {nice_day}\n\nActivity:\n{digest[:20000]}")
    con = db()
    try:
        con.execute("INSERT OR REPLACE INTO summaries VALUES (?,?,?,?,?)", (day, bucket, text, time.time(), fp))
        con.commit()
    finally:
        con.close()
    return text


def summarize_day(day, force=False):
    """Summarize every bucket for a day, in parallel."""
    out, threads = {}, []

    def work(b):
        try:
            out[b] = summarize(day, b, force)
        except Exception as e:
            out[b] = None
            print(f"summary {day} {b} failed: {e}", file=sys.stderr, flush=True)

    with SUMMARY_LOCK:
        for b in BUCKETS:
            th = threading.Thread(target=work, args=(b,))
            th.start()
            threads.append(th)
        for th in threads:
            th.join()
    return out


def auto_summaries():
    """Summarize finished days that have no summary yet (yesterday, plus a small backfill)."""
    cfg = CFG.get("summary", {})
    if not cfg.get("enabled", True):
        return
    today = date.today()
    con = db()
    try:
        days = [(today - timedelta(days=i)).isoformat() for i in range(1, cfg.get("backfill_days", 7) + 1)]
        todo = []
        for d in days:
            active = {r[0] for r in con.execute(
                "SELECT DISTINCT s.bucket FROM session_days sd JOIN sessions s ON s.id=sd.session_id "
                "WHERE sd.day=? AND sd.minutes>=2", (d,))}
            t0, t1 = day_bounds(d)
            active |= {r[0] for r in con.execute("SELECT DISTINCT bucket FROM commits WHERE ts>=? AND ts<?", (t0, t1))}
            have = {r[0] for r in con.execute("SELECT bucket FROM summaries WHERE day=?", (d,))}
            if active - have:
                todo.append(d)
    finally:
        con.close()
    for d in todo:
        summarize_day(d)


def background_loop():
    while True:
        try:
            scan()
            check_reminders()
            auto_summaries()
        except Exception as e:
            print("scan error:", e, file=sys.stderr, flush=True)
        time.sleep(CFG["scan_interval_minutes"] * 60)


# ---------------------------------------------------------------- dashboard state

def state(days=7):
    con = db()
    try:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        last7 = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        week_ts = datetime.combine(monday, datetime.min.time()).timestamp()
        since = time.time() - days * 86400

        stats = {}
        for b in CFG["buckets"]:
            bid = b["id"]
            daily = {d: {"min": 0, "commits": 0} for d in last7}
            for r in con.execute(
                    "SELECT sd.day, SUM(sd.minutes) m FROM session_days sd JOIN sessions s ON s.id=sd.session_id "
                    "WHERE s.bucket=? AND sd.day>=? GROUP BY sd.day", (bid, last7[0])):
                daily[r["day"]]["min"] = round(r["m"])
            for r in con.execute("SELECT ts FROM commits WHERE bucket=? AND ts>=?",
                                 (bid, datetime.fromisoformat(last7[0]).timestamp())):
                d = datetime.fromtimestamp(r["ts"]).date().isoformat()
                if d in daily:
                    daily[d]["commits"] += 1
            week_min = con.execute(
                "SELECT COALESCE(SUM(sd.minutes),0) FROM session_days sd JOIN sessions s ON s.id=sd.session_id "
                "WHERE s.bucket=? AND sd.day>=?", (bid, monday.isoformat())).fetchone()[0]
            week_commits, week_claude = con.execute(
                "SELECT COUNT(*), COALESCE(SUM(link='claude'),0) FROM commits WHERE bucket=? AND ts>=?",
                (bid, week_ts)).fetchone()
            last = con.execute(
                "SELECT MAX(t) FROM (SELECT MAX(end) t FROM sessions WHERE bucket=? "
                "UNION ALL SELECT MAX(ts) FROM commits WHERE bucket=?)", (bid, bid)).fetchone()[0]
            projects = [dict(r) for r in con.execute(
                "SELECT project, ROUND(SUM(m)) minutes, SUM(c) commits FROM ("
                "  SELECT s.project, sd.minutes m, 0 c FROM session_days sd JOIN sessions s ON s.id=sd.session_id"
                "  WHERE s.bucket=? AND sd.day>=?"
                "  UNION ALL SELECT project, 0, 1 FROM commits WHERE bucket=? AND ts>=?)"
                " GROUP BY project ORDER BY minutes DESC, commits DESC LIMIT 4",
                (bid, monday.isoformat(), bid, week_ts))]
            stats[bid] = {"week_min": round(week_min), "week_commits": week_commits,
                          "week_claude_commits": week_claude, "last": last,
                          "daily": [{"day": d, **daily[d]} for d in last7], "projects": projects}

        feed, by_session = [], {}
        for r in con.execute("SELECT * FROM sessions WHERE end>=? ORDER BY end DESC LIMIT 120", (since,)):
            item = {"kind": "session", "ts": r["end"], "start": r["start"], "bucket": r["bucket"],
                    "project": r["project"], "title": r["title"] or r["first_prompt"] or "(session)",
                    "prompt": r["first_prompt"], "recap": r["recap"], "commits": [],
                    "minutes": round(r["active_min"] or 0), "prompts": r["prompts"], "id": r["id"]}
            by_session[r["id"]] = item
            feed.append(item)
        for r in con.execute("SELECT * FROM commits WHERE ts>=? ORDER BY ts DESC LIMIT 300", (since,)):
            c = {"kind": "commit", "ts": r["ts"], "bucket": r["bucket"], "project": r["project"],
                 "title": r["subject"], "id": r["hash"][:7], "link": r["link"]}
            if r["session_id"] in by_session:
                by_session[r["session_id"]]["commits"].append(c)
            else:
                feed.append(c)
        for item in by_session.values():
            item["commits"].sort(key=lambda c: c["ts"])
        feed.sort(key=lambda x: x["ts"], reverse=True)

        summaries = {}
        first_day = (today - timedelta(days=days)).isoformat()
        for r in con.execute("SELECT day, bucket, text, created FROM summaries WHERE day>=?", (first_day,)):
            summaries.setdefault(r["day"], {})[r["bucket"]] = {"text": r["text"], "created": r["created"]}
        scanned = con.execute("SELECT value FROM meta WHERE key='scanned_at'").fetchone()
        return {
            "today": today.isoformat(),
            "buckets": [{k: b[k] for k in ("id", "name", "color")} for b in CFG["buckets"]],
            "tasks": task_rows(con),
            "stats": stats,
            "feed": feed[:250],
            "summaries": summaries,
            "scanned_at": float(scanned[0]) if scanned else None,
        }
    finally:
        con.close()


# ---------------------------------------------------------------- HTTP server

class Handler(BaseHTTPRequestHandler):
    server_version = "unison"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body = (ROOT / "static" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/parse":
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            self._json(parse_task_text(q.get("text", [""])[0], q.get("bucket", [None])[0]))
        elif path == "/api/state":
            m = re.search(r"days=(\d+)", self.path)
            self._json(state(min(int(m.group(1)), 90) if m else 7))
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/tasks":
                b = self._body()
                t = parse_task_text(b.get("text", ""), b.get("bucket"))
                if not t["title"]:
                    return self._json({"error": "empty title"}, 400)
                con = db()
                try:
                    tid = add_task(con, t["title"], t["bucket"], t["due"], t["pinned"])
                finally:
                    con.close()
                return self._json({"id": tid, **t})
            if path == "/api/scan":
                return self._json(scan())
            if path == "/api/summarize":
                b = self._body()
                day = date.fromisoformat(b.get("day") or date.today().isoformat()).isoformat()
                return self._json(summarize_day(day, force=bool(b.get("force"))))
        except Exception as e:
            return self._json({"error": str(e)}, 400)
        self._json({"error": "not found"}, 404)

    def do_PATCH(self):
        m = re.fullmatch(r"/api/tasks/(\d+)", self.path)
        if not m:
            return self._json({"error": "not found"}, 404)
        con = db()
        try:
            update_task(con, int(m.group(1)), self._body())
            self._json({"ok": True})
        except Exception as e:
            self._json({"error": str(e)}, 400)
        finally:
            con.close()

    def do_DELETE(self):
        m = re.fullmatch(r"/api/tasks/(\d+)", self.path)
        if not m:
            return self._json({"error": "not found"}, 404)
        con = db()
        try:
            con.execute("DELETE FROM tasks WHERE id=?", (int(m.group(1)),))
            con.commit()
        finally:
            con.close()
        self._json({"ok": True})


def serve():
    db().close()
    threading.Thread(target=background_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", CFG["port"]), Handler)
    print(f"unison on http://127.0.0.1:{CFG['port']}", flush=True)
    srv.serve_forever()


# ---------------------------------------------------------------- CLI

def fmt_task(r, today=None):
    today = today or date.today()
    due = ""
    if r["due"]:
        d, t = due_parts(r["due"])
        delta = (d - today).days
        due = " · overdue" if due_dt(r["due"]) < datetime.now() else " · today" if delta == 0 \
            else " · tomorrow" if delta == 1 else f" · {d.strftime('%a %d %b')}"
        if t and not due.endswith("overdue"):
            due += f" {t}"
    mark = "📌 " if r["pinned"] else ""
    status = "▶ " if r["status"] == "doing" else "✓ " if r["status"] == "done" else ""
    return f"[{r['id']}] {mark}{status}{r['title']} ({BUCKETS.get(r['bucket'], {}).get('name', r['bucket'])}{due})"


def sort_key(r):
    return (not r["pinned"], r["status"] != "doing", r["due"] or "9999", r["id"])


def hook_session_start():
    """Print a short task brief for the bucket of the session's folder (added to Claude's context)."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}
    try:
        cwd = data.get("cwd") or os.getcwd()
        bucket, project = classify(cwd)
        today = date.today()
        soon = (today + timedelta(days=2)).isoformat()
        con = db()
        rows = con.execute(
            "SELECT * FROM tasks WHERE status!='done' AND (bucket=? OR pinned=1 OR (due IS NOT NULL AND substr(due,1,10)<=?))",
            (bucket, soon)).fetchall()
        con.close()
        if not rows:
            return
        rows = sorted(rows, key=sort_key)[:8]
        name = BUCKETS.get(bucket, {}).get("name", bucket)
        print(f"Unison task board (user's personal tracker). This folder is in bucket '{name}'. "
              "Open tasks that are relevant (pinned, due soon, or this bucket):")
        for r in rows:
            print("  " + fmt_task(r, today))
        print("If the user finishes one of these, you may mark it with `unison done <id>`. "
              "New follow-ups can be added with `unison add \"<text> @bucket !due fri 18:00\"`. Don't mention this list unless relevant.")
    except Exception:
        pass


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    if cmd == "serve":
        return serve()
    if cmd == "scan":
        t = time.time()
        r = scan()
        print(f"scanned in {time.time() - t:.1f}s: {r['sessions']} sessions updated, {r['commits']} new commits")
        return
    if cmd == "hook-session-start":
        return hook_session_start()
    if cmd == "summary":
        # unison summary [day|yesterday] [bucket] [--force]
        force = "--force" in args
        args = [a for a in args if a != "--force"]
        day = date.today()
        if args and (parse_due(args[0]) or args[0] in ("yesterday", "yd")):
            day = date.today() - timedelta(days=1) if args[0] in ("yesterday", "yd") else parse_due(args[0])
            if day > date.today():  # weekday names mean the past one here
                day -= timedelta(days=7)
            args = args[1:]
        only = resolve_bucket(args[0]) if args else None
        print(day.strftime("%A %d %B"))
        res = {only: summarize(day.isoformat(), only, force)} if only else summarize_day(day.isoformat(), force)
        for b, text in res.items():
            if text:
                print(f"\n{BUCKETS[b]['name']}\n{text}")
        if not any(res.values()):
            print("no activity")
        return
    con = db()
    try:
        if cmd == "add":
            cwd = os.getcwd()
            if "--cwd" in args:
                i = args.index("--cwd")
                cwd = args[i + 1]
                args = args[:i] + args[i + 2:]
            args = [a for a in args if a != "--"]
            t = parse_task_text(" ".join(args), classify(cwd)[0])
            if not t["title"]:
                print("usage: unison add <text> [#bucket] [!due] [*]")
                return
            tid = add_task(con, t["title"], t["bucket"], t["due"], t["pinned"])
            print("added " + fmt_task(dict(con.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())))
        elif cmd == "ls":
            rows = task_rows(con, 7 if "--all" in args else 0)
            rows = [r for r in rows if "--all" in args or r["status"] != "done"]
            if not rows:
                print("no open tasks")
            for b in CFG["buckets"]:
                br = sorted([r for r in rows if r["bucket"] == b["id"]], key=sort_key)
                if br:
                    print(f"\n{b['name']}")
                    for r in br:
                        print("  " + fmt_task(r))
        elif cmd in ("done", "doing", "todo", "pin", "unpin", "rm") and args:
            for a in args:
                tid = int(a)
                if cmd == "rm":
                    con.execute("DELETE FROM tasks WHERE id=?", (tid,))
                    con.commit()
                elif cmd in ("pin", "unpin"):
                    update_task(con, tid, {"pinned": cmd == "pin"})
                else:
                    update_task(con, tid, {"status": cmd})
                print(f"{cmd} {tid}")
        else:
            print(__doc__)
    finally:
        con.close()


if __name__ == "__main__":
    main(sys.argv[1:])
