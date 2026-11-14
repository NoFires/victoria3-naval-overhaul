#!/usr/bin/env python3
"""
Victoria 3 Live Observer & Log Monitor
Samples Victoria 3 logs (error*.log, game.log, debug.log, gui.log, dedicated_server.log,
custom_automated_stats.log) periodically or in batch, separating Mod/Naval issues from
known Vanilla noise, and inspecting autosave/date progression.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

V3_DOC_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "Paradox Interactive" / "Victoria 3"
LOGS_DIR = V3_DOC_DIR / "logs"

MOD_HIGHLIGHT_RE = re.compile(
    r"(naval_overhaul|ship_mod|ship_type|ship_designer|utility_mod|je_naval|naval_battle_size|"
    r"navy_model|naval_mission|ship_veterancy|01_naval|zz_naval|02_hull|03_overhaul|00_ship_|"
    r"ShipTemplate|ShipDesigner|NavalOverhaul|Naval Overhaul|NAVAL_BATTLE_SIZE_RECON_ADVANTAGE)",
    re.I,
)

NAVAL_AI_RE = re.compile(
    r"(ship|naval|navy|fleet|admiral|blockade|bombard|convoy|submarine|dreadnought|destroyer|"
    r"ai_strateg|max_ship_design_complexity|script_value|gui/|localization)",
    re.I,
)

KNOWN_VANILLA_NOISE_SUBSTRS = (
    "lawgroup_navy_model has no active law",
    "01_natural_borders_of_france.txt",
    "events/train_events.txt",
    "communist_fascist_election_events.txt",
    "ig_revolutions.txt",
    "00_character_interactions.txt",
    "00_communism.txt",
    "BATTLE_SHIPS_BREAKDOWN_HEADER_ATTACKER",
    "BATTLE_SHIPS_BREAKDOWN_HEADER_DEFENDER",
    "CalcCurrentAttackerCombatPower",
    "CalcCurrentDefenderCombatPower",
    "Failed to find a travel position for HQ",
)


def is_v3_running() -> Tuple[bool, str]:
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process -Name 'victoria3' -ErrorAction SilentlyContinue | Select-Object -First 1 Id,WorkingSet64,CPU | ConvertTo-Json -Compress"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return True, out
    except Exception:
        pass
    return False, ""


def split_log_blocks(text: str) -> List[str]:
    if not text.strip():
        return []
    blocks = re.split(r"\r?\n(?=\[\d{2}:\d{2}:\d{2}\])", text.strip())
    return [b.strip() for b in blocks if b.strip()]


def normalize_block(block: str) -> str:
    return re.sub(r"^\[\d{2}:\d{2}:\d{2}\]", "", block).strip()


def latest_game_date() -> str:
    # Check custom_automated_stats.log, dedicated_server.log, or save games
    dserv = LOGS_DIR / "dedicated_server.log"
    if dserv.exists():
        tail = dserv.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
        for line in reversed(tail):
            m = re.search(r"Processing Tick:\s*([0-9.]+)", line)
            if m:
                return f"Tick {m.group(1)}"
    stats = LOGS_DIR / "custom_automated_stats.log"
    if stats.exists():
        tail = stats.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        for line in reversed(tail):
            m = re.search(r"\[Year\]\[[^\]]+\]:\[[^\]]+\]\[(\d+)\]", line)
            if m:
                return f"Year {m.group(1)}"
    return "Unknown (loading / paused / menu)"


def analyze_logs(since_ts: float = 0.0, include_rotated: bool = False) -> Dict[str, object]:
    if include_rotated or since_ts > 0.0:
        error_files = sorted(
            [f for f in LOGS_DIR.glob("error*.log") if f.stat().st_mtime >= since_ts],
            key=lambda p: p.stat().st_mtime,
        )
    else:
        cur = LOGS_DIR / "error.log"
        error_files = [cur] if cur.exists() else []
    mod_errors: Counter[str] = Counter()
    mod_samples: Dict[str, str] = {}
    naval_errors: Counter[str] = Counter()
    naval_samples: Dict[str, str] = {}
    other_errors: Counter[str] = Counter()
    other_samples: Dict[str, str] = {}
    total_blocks = 0

    for ef in error_files:
        txt = ef.read_text(encoding="utf-8", errors="replace")
        for blk in split_log_blocks(txt):
            total_blocks += 1
            norm = normalize_block(blk)
            sig = " | ".join(norm.splitlines()[:2])[:220]
            if MOD_HIGHLIGHT_RE.search(norm):
                mod_errors[sig] += 1
                mod_samples.setdefault(sig, norm[:500])
            elif any(noise in norm for noise in KNOWN_VANILLA_NOISE_SUBSTRS):
                continue
            elif NAVAL_AI_RE.search(norm):
                naval_errors[sig] += 1
                naval_samples.setdefault(sig, norm[:500])
            else:
                other_errors[sig] += 1
                other_samples.setdefault(sig, norm[:350])

    gui_issues: List[str] = []
    gui_log = LOGS_DIR / "gui.log"
    if gui_log.exists() and gui_log.stat().st_mtime >= since_ts:
        for line in gui_log.read_text(encoding="utf-8", errors="replace").splitlines():
            if any(k in line.lower() for k in ("error", "warn", "ship_designer", "failed")):
                gui_issues.append(line[:250])

    db_conflicts: List[str] = []
    db_log = LOGS_DIR / "database_conflicts.log"
    if db_log.exists() and db_log.stat().st_mtime >= since_ts:
        for line in db_log.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                db_conflicts.append(line[:250])

    return {
        "files_scanned": [f.name for f in error_files],
        "total_blocks": total_blocks,
        "mod_errors": mod_errors,
        "mod_samples": mod_samples,
        "naval_errors": naval_errors,
        "naval_samples": naval_samples,
        "other_errors": other_errors,
        "other_samples": other_samples,
        "gui_issues": gui_issues,
        "db_conflicts": db_conflicts,
        "game_date": latest_game_date(),
    }


def print_snapshot(res: Dict[str, object], verbose: bool = False) -> None:
    running, proc_info = is_v3_running()
    ts = datetime.now().strftime("%H:%M:%S")
    mod_e: Counter[str] = res["mod_errors"]  # type: ignore[assignment]
    nav_e: Counter[str] = res["naval_errors"]  # type: ignore[assignment]
    oth_e: Counter[str] = res["other_errors"]  # type: ignore[assignment]
    gui_i: List[str] = res["gui_issues"]  # type: ignore[assignment]
    db_c: List[str] = res.get("db_conflicts", [])  # type: ignore[assignment]

    print(
        f"[{ts}] V3={'RUNNING' if running else 'STOPPED'} | Date={res['game_date']} | "
        f"TotalErrBlocks={res['total_blocks']} | ModErrs={sum(mod_e.values())} ({len(mod_e)} uniq) | "
        f"Naval/GUI/AIErrs={sum(nav_e.values())} ({len(nav_e)} uniq) | OtherUniq={len(oth_e)} | GuiLog={len(gui_i)} | DbConf={len(db_c)}"
    )
    if proc_info and verbose:
        print(f"  Proc: {proc_info}")

    if mod_e:
        print("  [MOD ERRORS]:")
        for sig, cnt in mod_e.most_common(15):
            print(f"    [{cnt}x] {res['mod_samples'][sig]}")  # type: ignore[index]

    if nav_e and verbose:
        print("  [NAVAL / GUI / AI ERRORS (non-noise)]:")
        for sig, cnt in nav_e.most_common(15):
            print(f"    [{cnt}x] {res['naval_samples'][sig]}")  # type: ignore[index]

    if gui_i and verbose:
        print("  [GUI LOG HIGHLIGHTS]:")
        for line in gui_i[:10]:
            print(f"    {line}")

    if db_c and verbose:
        print("  [DATABASE CONFLICTS]:")
        for line in db_c[:20]:
            print(f"    {line}")

    if oth_e and verbose:
        print("  [TOP OTHER ERRORS]:")
        for sig, cnt in oth_e.most_common(10):
            print(f"    [{cnt}x] {res['other_samples'][sig]}")  # type: ignore[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Victoria 3 live observer & error.log sampler")
    parser.add_argument("--interval", type=int, default=20, help="Polling interval in seconds")
    parser.add_argument("--duration", type=int, default=0, help="Total monitor duration in seconds (0 = single snapshot)")
    parser.add_argument("--since-epoch", type=float, default=0.0, help="Only inspect logs modified after this Unix timestamp")
    parser.add_argument("--verbose", action="store_true", help="Print detailed error samples")
    parser.add_argument("--stop-when-exits", action="store_true", help="Exit loop once victoria3 process exits")
    parser.add_argument("--include-rotated", action="store_true", help="Also scan rotated error.*.log files")
    args = parser.parse_args()

    if not LOGS_DIR.exists():
        print(f"ERROR: Victoria 3 logs dir not found: {LOGS_DIR}", file=sys.stderr)
        return 1

    if args.duration <= 0:
        res = analyze_logs(args.since_epoch, include_rotated=args.include_rotated)
        print_snapshot(res, verbose=True)
        return 0

    end_time = time.time() + args.duration
    seen_mod: Set[str] = set()
    seen_nav: Set[str] = set()
    saw_running = False

    print(f"Monitoring Victoria 3 logs at {LOGS_DIR} every {args.interval}s for up to {args.duration}s...")
    while time.time() < end_time:
        running, _ = is_v3_running()
        if running:
            saw_running = True
        res = analyze_logs(args.since_epoch, include_rotated=args.include_rotated)
        print_snapshot(res, verbose=False)

        mod_e: Counter[str] = res["mod_errors"]  # type: ignore[assignment]
        nav_e: Counter[str] = res["naval_errors"]  # type: ignore[assignment]
        for sig in mod_e:
            if sig not in seen_mod:
                seen_mod.add(sig)
                print(f"  [NEW MOD ERR] {res['mod_samples'][sig]}")  # type: ignore[index]
        for sig in nav_e:
            if sig not in seen_nav:
                seen_nav.add(sig)
                print(f"  [NEW NAVAL/GUI/AI ERR] {res['naval_samples'][sig]}")  # type: ignore[index]

        if args.stop_when_exits and saw_running and not running:
            print("Victoria 3 exited; finishing monitor.")
            break
        time.sleep(args.interval)

    print("\n=== FINAL BATCH LOG SUMMARY ===")
    final_res = analyze_logs(args.since_epoch, include_rotated=args.include_rotated)
    print_snapshot(final_res, verbose=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
