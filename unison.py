#!/usr/bin/env python3
"""Unison: a tiny local work tracker.

Tasks you write down + Claude Code sessions + git commits, grouped into
buckets (Forte, Uni, ArqaMed, ZAP, ...). Standard library only.

  unison serve                  run the dashboard + background scanner
  unison scan                   scan sessions and commits once
  unison add <text> [--cwd D]   add a task  (#bucket  !due  * = pin)
  unison ls [--all]             list open tasks
  unison done|pin|doing|rm <id>
  unison hook-session-start     Claude Code SessionStart hook (reads JSON on stdin)
"""
import fnmatch
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
CREATE INDEX IF NOT EXISTS idx_sd_day ON session_days(day);
CREATE INDEX IF NOT EXISTS idx_commits_ts ON commits(ts);
CREATE INDEX IF NOT EXISTS idx_sessions_end ON sessions(end);
"""


def db():
    DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
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


def resolve_bucket(name):
    n = name.lower()
    for b in CFG["buckets"]:
        if n == b["id"] or n == b["name"].lower() or n in b.get("aliases", []):
            return b["id"]
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


def parse_task_text(text, default_bucket=None):
    title, bucket, due, pinned = [], None, None, False
    for tok in text.split():
        if tok.startswith("#") and len(tok) > 1 and resolve_bucket(tok[1:]):
            bucket = resolve_bucket(tok[1:])
        elif tok.startswith("!") and len(tok) > 1 and parse_due(tok[1:]):
            due = parse_due(tok[1:])
        elif tok in ("*", "!pin", "📌"):
            pinned = True
        else:
            title.append(tok)
    return {
        "title": " ".join(title).strip(),
        "bucket": bucket or default_bucket or CFG["default_bucket"],
        "due": due.isoformat() if due else None,
        "pinned": pinned,
    }


# ---------------------------------------------------------------- tasks

def add_task(con, title, bucket, due=None, pinned=False):
    now = time.time()
    cur = con.execute(
        "INSERT INTO tasks (title, bucket, due, pinned, status, created, updated) VALUES (?,?,?,?,?,?,?)",
        (title, bucket, due, int(bool(pinned)), "todo", now, now))
    con.commit()
    return cur.lastrowid


def update_task(con, tid, fields):
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
            v = date.fromisoformat(v).isoformat()
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
                    "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (s["id"], bucket, project, s["cwd"], s["title"], s["first_prompt"], s["recap"],
                     s["start"], s["end"], s["active_min"], s["prompts"], s["cost"]))
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
        con.executemany("INSERT OR IGNORE INTO commits VALUES (?,?,?,?,?,?)", rows)
        added += con.total_changes - before
    con.commit()
    return added


def scan():
    with SCAN_LOCK:
        con = db()
        try:
            _repo_cache.clear()
            s = scan_sessions(con)
            c = scan_commits(con)
            reclassify(con)
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
    n = CFG.get("notify", {})
    if not n.get("enabled", True) or datetime.now().hour < n.get("hour", 9):
        return
    today = date.today()
    con = db()
    try:
        rows = con.execute(
            "SELECT * FROM tasks WHERE status!='done' AND due IS NOT NULL AND due<=? "
            "AND id NOT IN (SELECT task_id FROM notified WHERE day=?) ORDER BY due",
            ((today + timedelta(days=1)).isoformat(), today.isoformat())).fetchall()
        if not rows:
            return
        lines = []
        for r in rows:
            d = date.fromisoformat(r["due"])
            when = "overdue" if d < today else "today" if d == today else "tomorrow"
            lines.append(f"• {r['title']} ({BUCKETS.get(r['bucket'], {}).get('name', r['bucket'])}, {when})")
        send_notification(f"{len(rows)} task{'s' if len(rows) > 1 else ''} due", "\n".join(lines))
        con.executemany("INSERT OR IGNORE INTO notified VALUES (?,?)",
                        [(r["id"], today.isoformat()) for r in rows])
        con.commit()
    finally:
        con.close()


def background_loop():
    while True:
        try:
            scan()
            check_reminders()
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
            week_commits = con.execute("SELECT COUNT(*) FROM commits WHERE bucket=? AND ts>=?",
                                       (bid, week_ts)).fetchone()[0]
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
            stats[bid] = {"week_min": round(week_min), "week_commits": week_commits, "last": last,
                          "daily": [{"day": d, **daily[d]} for d in last7], "projects": projects}

        feed = []
        for r in con.execute("SELECT * FROM sessions WHERE end>=? ORDER BY end DESC LIMIT 120", (since,)):
            feed.append({"kind": "session", "ts": r["end"], "start": r["start"], "bucket": r["bucket"],
                         "project": r["project"], "title": r["title"] or r["first_prompt"] or "(session)",
                         "prompt": r["first_prompt"], "recap": r["recap"],
                         "minutes": round(r["active_min"] or 0), "prompts": r["prompts"], "id": r["id"]})
        for r in con.execute("SELECT * FROM commits WHERE ts>=? ORDER BY ts DESC LIMIT 200", (since,)):
            feed.append({"kind": "commit", "ts": r["ts"], "bucket": r["bucket"], "project": r["project"],
                         "title": r["subject"], "id": r["hash"][:8]})
        feed.sort(key=lambda x: x["ts"], reverse=True)

        scanned = con.execute("SELECT value FROM meta WHERE key='scanned_at'").fetchone()
        return {
            "today": today.isoformat(),
            "buckets": [{k: b[k] for k in ("id", "name", "color")} for b in CFG["buckets"]],
            "tasks": task_rows(con),
            "stats": stats,
            "feed": feed[:250],
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
        d = date.fromisoformat(r["due"])
        delta = (d - today).days
        due = " · overdue" if delta < 0 else " · today" if delta == 0 else " · tomorrow" if delta == 1 \
            else f" · {d.strftime('%a %d %b')}"
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
            "SELECT * FROM tasks WHERE status!='done' AND (bucket=? OR pinned=1 OR (due IS NOT NULL AND due<=?))",
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
              "New follow-ups can be added with `unison add \"<text> #bucket !due\"`. Don't mention this list unless relevant.")
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
