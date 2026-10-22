#!/usr/bin/env bash
# User-level install (no sudo): CLI, startup service, Claude Code /todo + SessionStart hook.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR/data" ~/.local/bin ~/.config/systemd/user ~/.claude/commands

ln -sf "$DIR/unison.py" ~/.local/bin/unison
cp "$DIR/deploy/unison.service" ~/.config/systemd/user/unison.service
systemctl --user daemon-reload
systemctl --user enable --now unison.service
systemctl --user restart unison.service

cp "$DIR/claude/todo.md" ~/.claude/commands/todo.md
mkdir -p ~/.claude/skills
ln -sfn "$DIR/claude/skills/unison" ~/.claude/skills/unison

# Add SessionStart hook to ~/.claude/settings.json (idempotent, keeps a backup).
python3 - "$DIR" <<'PY'
import json, shutil, sys, pathlib
p = pathlib.Path.home() / ".claude" / "settings.json"
cfg = json.loads(p.read_text()) if p.exists() else {}
cmd = f"python3 {sys.argv[1]}/unison.py hook-session-start"
hooks = cfg.setdefault("hooks", {}).setdefault("SessionStart", [])
if not any(h.get("command") == cmd for e in hooks for h in e.get("hooks", [])):
    if p.exists():
        shutil.copy(p, p.with_suffix(".json.bak-unison"))
    hooks.append({"hooks": [{"type": "command", "command": cmd, "timeout": 5}]})
    p.write_text(json.dumps(cfg, indent=2) + "\n")
    print("added SessionStart hook")
else:
    print("SessionStart hook already present")
PY

echo "Unison running on http://127.0.0.1:7477"
echo "For http://unison run once:  sudo $DIR/install-system.sh"
