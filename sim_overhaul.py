#!/usr/bin/env python3
"""
Victoria 3 Naval Overhaul — .txt-Driven VFS & Simulation Tool
Zero external dependencies (Python 3 stdlib only).
Directly parses Vanilla + companion mods + Mod .txt/.yml/.gui files.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_VANILLA_DIR = Path(
    os.environ.get("V3_GAME_DIR", r"C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game")
)
MOD_DIR = Path(__file__).resolve().parent
DEFAULT_KUROMI_DIR = Path(
    os.environ.get("V3_KUROMI_DIR", r"C:\Program Files (x86)\Steam\steamapps\workshop\content\529340\3227982912")
)
DEFAULT_NTE_DIR = Path(
    os.environ.get("V3_NTE_DIR", r"C:\Users\RedAndBlack\Documents\Paradox Interactive\Victoria 3\mod\Naval Treaty Expanded")
)


# =============================================================================
# 1. Clausewitz .txt Lexer, Parser & VFS Merger (INJECT / TRY_INJECT / REPLACE)
# =============================================================================

TOKEN_RE = re.compile(
    r'"(?:\\.|[^"\\])*"'
    r'|<=|>=|!=|==|<|>|='
    r'|\{|\}'
    r'|[^\s\{\}=<>!]+'
)


def strip_comments(text: str) -> str:
    out_lines: List[str] = []
    for line in text.splitlines():
        in_str = False
        escaped = False
        cut = len(line)
        for i, ch in enumerate(line):
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_str:
                escaped = True
            elif ch == '"':
                in_str = not in_str
            elif ch == "#" and not in_str:
                cut = i
                break
        out_lines.append(line[:cut])
    return "\n".join(out_lines)


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(strip_comments(text))


def _unquote(tok: str) -> str:
    if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
        return tok[1:-1]
    return tok


def _to_scalar(tok: str, vars_map: Dict[str, Any]) -> Any:
    raw = _unquote(tok)
    if raw.startswith("@") and raw in vars_map:
        return vars_map[raw]
    if raw == "yes":
        return True
    if raw == "no":
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def parse_clausewitz(text: str, vars_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    tokens = tokenize(text)
    n = len(tokens)
    pos = 0
    local_vars: Dict[str, Any] = dict(vars_map) if vars_map else {}

    def parse_block() -> Any:
        nonlocal pos
        items: List[Tuple[str, str, Any]] = []
        bare_list: List[Any] = []
        while pos < n:
            tok = tokens[pos]
            if tok == "}":
                pos += 1
                break
            if tok == "{":
                pos += 1
                bare_list.append(parse_block())
                continue
            if pos + 1 < n and tokens[pos + 1] in ("=", "<", ">", "<=", ">=", "!=", "=="):
                key = _unquote(tok)
                op = tokens[pos + 1]
                pos += 2
                if pos < n and tokens[pos] == "{":
                    pos += 1
                    val = parse_block()
                elif pos < n:
                    val = _to_scalar(tokens[pos], local_vars)
                    pos += 1
                else:
                    val = None
                if key.startswith("@") and op == "=" and not isinstance(val, (dict, list)):
                    local_vars[key] = val
                else:
                    items.append((key, op, val))
            else:
                bare_list.append(_to_scalar(tok, local_vars))
                pos += 1

        if items and not bare_list:
            out: Dict[str, Any] = {}
            for k, op, v in items:
                val = v if op == "=" else {"_op": op, "_val": v}
                if k in out:
                    if isinstance(out[k], list):
                        out[k].append(val)
                    else:
                        out[k] = [out[k], val]
                else:
                    out[k] = val
            return out
        if bare_list and not items:
            return bare_list
        if not items and not bare_list:
            return {}
        out = {"_list": bare_list}
        for k, op, v in items:
            val = v if op == "=" else {"_op": op, "_val": v}
            if k in out:
                if isinstance(out[k], list):
                    out[k].append(val)
                else:
                    out[k] = [out[k], val]
            else:
                out[k] = val
        return out

    res = parse_block()
    return res if isinstance(res, dict) else {}


def _merge_script_value_block(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    """Merge additive script_value instructions (e.g. max_ship_design_complexity in INJECT)."""
    merged = dict(dst)
    if "value" in src and isinstance(src["value"], (int, float)):
        merged["value"] = src["value"]
    extra_adds = merged.get("_injected_adds", [])
    if not isinstance(extra_adds, list):
        extra_adds = [extra_adds]
    if "add" in src:
        adds = src["add"] if isinstance(src["add"], list) else [src["add"]]
        extra_adds.extend(adds)
    if "if" in src:
        merged.setdefault("_injected_ifs", [])
        ifs = src["if"] if isinstance(src["if"], list) else [src["if"]]
        merged["_injected_ifs"].extend(ifs)
    if extra_adds:
        merged["_injected_adds"] = extra_adds
    return merged


def deep_inject(
    dst: Dict[str, Any],
    src: Dict[str, Any],
    warnings: Optional[List[str]] = None,
    context_label: str = "",
) -> Dict[str, Any]:
    """Jomini INJECT / TRY_INJECT semantics: containers merge/append, script_values accumulate."""
    for k, v in src.items():
        if k not in dst:
            dst[k] = v
        elif isinstance(dst[k], dict) and isinstance(v, dict):
            if k in ("modifier", "command_modifier"):
                for mk, mv in v.items():
                    if isinstance(mv, (int, float)) and isinstance(dst[k].get(mk), (int, float)):
                        dst[k][mk] = dst[k][mk] + mv
                    else:
                        dst[k][mk] = mv
            elif k == "max_ship_design_complexity":
                dst[k] = _merge_script_value_block(dst[k], v)
            elif k in ("ai_weight", "potential", "possible", "unlocking_technologies"):
                dst[k] = v
            else:
                deep_inject(dst[k], v, warnings, f"{context_label}.{k}" if context_label else k)
        elif isinstance(dst[k], list) and isinstance(v, list):
            dst[k].extend(v)
        elif isinstance(dst[k], list):
            dst[k].append(v)
        else:
            dst[k] = v
    return dst


def merge_clausewitz_tree(base: Dict[str, Any], incoming: Dict[str, Any], warnings: List[str], source_name: str) -> None:
    for raw_key, val in incoming.items():
        if ":" in raw_key:
            prefix, target = raw_key.split(":", 1)
            if prefix in ("INJECT", "TRY_INJECT", "INJECT_OR_CREATE"):
                if target in base and isinstance(base[target], dict) and isinstance(val, dict):
                    deep_inject(base[target], val, warnings, f"{source_name}:{target}")
                elif prefix in ("TRY_INJECT", "INJECT_OR_CREATE"):
                    if prefix == "INJECT_OR_CREATE" and isinstance(val, dict):
                        base[target] = val
                else:
                    warnings.append(f"[{source_name}] INJECT target not found: {target}")
            elif prefix in ("REPLACE", "TRY_REPLACE", "REPLACE_OR_CREATE"):
                if target in base or prefix in ("TRY_REPLACE", "REPLACE_OR_CREATE"):
                    base[target] = val
                else:
                    warnings.append(f"[{source_name}] REPLACE target not found: {target}")
            else:
                base[raw_key] = val
        else:
            base[raw_key] = val


def load_scripted_variables(roots: List[Path]) -> Dict[str, Any]:
    vars_map: Dict[str, Any] = {}
    vfs_files: Dict[str, Path] = {}
    for root in roots:
        folder = root / "common" / "scripted_variables"
        if folder.exists():
            for f in sorted(folder.glob("*.txt"), key=lambda p: p.name):
                vfs_files[f.name] = f
    for fname in sorted(vfs_files.keys()):
        text = vfs_files[fname].read_text(encoding="utf-8-sig", errors="replace")
        for line in strip_comments(text).splitlines():
            m = re.match(r"^\s*(@[A-Za-z0-9_]+)\s*=\s*([^\s#]+)", line)
            if m:
                vars_map[m.group(1)] = _to_scalar(m.group(2), vars_map)
    return vars_map


def load_vfs_folder(
    roots: List[Path],
    rel_folder: str,
    warnings: List[str],
    global_vars: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Simulate Victoria 3 VFS: same relative path overrides earlier root; files load in ASCII order."""
    vfs_files: Dict[str, Path] = {}
    for root in roots:
        folder = root / rel_folder
        if not folder.exists():
            continue
        for f in sorted(folder.glob("*.txt"), key=lambda p: p.name):
            vfs_files[f.name] = f

    merged: Dict[str, Any] = {}
    for fname in sorted(vfs_files.keys()):
        fpath = vfs_files[fname]
        text = fpath.read_text(encoding="utf-8-sig", errors="replace")
        parsed = parse_clausewitz(text, global_vars)
        merge_clausewitz_tree(merged, parsed, warnings, f"{fpath.parent.parent.name}/{rel_folder}/{fname}")
    return merged


def load_defines(roots: List[Path]) -> Dict[str, Dict[str, Any]]:
    vfs_files: Dict[str, Path] = {}
    for root in roots:
        folder = root / "common" / "defines"
        if folder.exists():
            for f in sorted(folder.glob("*.txt"), key=lambda p: p.name):
                vfs_files[f.name] = f
    defines: Dict[str, Dict[str, Any]] = {}
    for fname in sorted(vfs_files.keys()):
        text = vfs_files[fname].read_text(encoding="utf-8-sig", errors="replace")
        parsed = parse_clausewitz(text)
        for sec, body in parsed.items():
            if isinstance(body, dict):
                defines.setdefault(sec, {}).update(body)
    return defines


def load_localization_with_dupes(root: Path, lang: str) -> Tuple[Dict[str, str], List[str]]:
    loc: Dict[str, str] = {}
    dupes: List[str] = []
    folder = root / "localization" / lang
    if not folder.exists():
        return loc, dupes
    pat = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"((?:\\.|[^"\\])*)"')
    for f in sorted(folder.glob("*.yml")):
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = pat.match(line)
            if m:
                key = m.group(1)
                if key in loc:
                    dupes.append(f"{f.name}:{key}")
                loc[key] = m.group(2)
    return loc, dupes


def load_vanilla_modifier_definitions(vanilla_dir: Path) -> Set[str]:
    defs: Set[str] = set()
    folder = vanilla_dir / "common" / "modifier_type_definitions"
    if not folder.exists():
        return defs
    pat = re.compile(r"^([a-z0-9_]+)\s*=\s*\{", re.M)
    for f in sorted(folder.glob("*.txt")):
        defs.update(pat.findall(f.read_text(encoding="utf-8-sig", errors="replace")))
    return defs


# =============================================================================
# 2. Data Model & Extraction from Parsed VFS
# =============================================================================

@dataclass
class ShipSpec:
    ship_id: str
    group: str
    cost_progress: float
    hp_max: float
    crew_max: float
    hull_dmg: float
    crew_dmg: float
    armor: float
    speed: float
    accuracy: float
    visibility: float
    detection: float
    crit_chance: float
    crit_mult: float
    vulnerability: float
    screening: float
    readiness_gain: float
    supply_capacity: float
    supply_cost_mult: float
    suffered_accuracy_mult: float
    suffered_hull_damage_mult: float
    suffered_crew_damage_mult: float
    suffered_crit_chance_mult: float
    blockade_strength: float
    blockade_mult: float
    power_projection: float
    mod_levels: int
    construction_level_mult: float
    materiel_goods: Dict[str, float] = field(default_factory=dict)
    construction_goods: Dict[str, float] = field(default_factory=dict)
    vs_type_acc_mult: Dict[str, float] = field(default_factory=dict)
    vs_type_hull_mult: Dict[str, float] = field(default_factory=dict)
    selected_mods: Dict[str, str] = field(default_factory=dict)


def _as_list(val: Any) -> List[Any]:
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def _sum_mod(dst: Dict[str, float], mod_block: Dict[str, Any]) -> None:
    if not isinstance(mod_block, dict):
        return
    for k, v in mod_block.items():
        if isinstance(v, (int, float)):
            dst[k] = dst.get(k, 0.0) + float(v)


def _sum_goods(dst: Dict[str, float], goods_block: Dict[str, Any]) -> None:
    if not isinstance(goods_block, dict):
        return
    for k, v in goods_block.items():
        if k.startswith("goods_input_") and k.endswith("_add") and isinstance(v, (int, float)):
            g = k[len("goods_input_"):-len("_add")]
            dst[g] = dst.get(g, 0.0) + float(v)


def get_ship_slot_pools(ship_def: Dict[str, Any]) -> Dict[str, List[str]]:
    pools: Dict[str, List[str]] = {}
    mods_blk = ship_def.get("modifications", {})
    if isinstance(mods_blk, dict):
        for slot_id, mod_list in mods_blk.items():
            if isinstance(mod_list, list):
                pools[slot_id] = [str(m) for m in mod_list]
    return pools


def get_default_mods(ship_def: Dict[str, Any]) -> Dict[str, str]:
    dm = ship_def.get("default_modifications", {})
    if isinstance(dm, dict):
        return {str(k): str(v) for k, v in dm.items()}
    return {}


def compute_mod_level(slot_id: str, mod_id: str, ship_def: Dict[str, Any], mods_db: Dict[str, Any]) -> int:
    """Estimate Victoria 3 modification level: core slot ordinal (1..N) or utility cost tier (1..2)."""
    if slot_id.startswith("ship_mod_slot_utility"):
        mdef = mods_db.get(mod_id, {})
        has_tech = bool(mdef.get("unlocking_technologies")) if isinstance(mdef, dict) else False
        return 2 if has_tech else 1
    pools = get_ship_slot_pools(ship_def)
    pool = pools.get(slot_id, [])
    if mod_id in pool:
        return pool.index(mod_id) + 1
    return 1


def build_ship_spec(
    ship_id: str,
    ship_def: Dict[str, Any],
    mods_db: Dict[str, Dict[str, Any]],
    selected_mods: Dict[str, str],
    mod_cost_factor: float = 1.028,
) -> ShipSpec:
    stats: Dict[str, float] = {}
    _sum_mod(stats, ship_def.get("modifier", {}))

    materiel: Dict[str, float] = {}
    constr: Dict[str, float] = {}
    _sum_goods(materiel, ship_def.get("materiel_goods", {}))
    _sum_goods(constr, ship_def.get("construction_goods", {}))

    mod_levels = 0
    for slot_id, mod_id in selected_mods.items():
        mdef = mods_db.get(mod_id)
        if not isinstance(mdef, dict):
            continue
        _sum_mod(stats, mdef.get("modifier", {}))
        _sum_goods(materiel, mdef.get("materiel_goods", {}))
        _sum_goods(constr, mdef.get("construction_goods", {}))
        mod_levels += compute_mod_level(slot_id, mod_id, ship_def, mods_db)

    hp_max = stats.get("ship_hit_points_max_add", 100.0) * (1.0 + stats.get("ship_hit_points_max_mult", 0.0))
    crew_max = stats.get("ship_crew_max_add", 100.0) * (1.0 + stats.get("ship_crew_max_mult", 0.0))
    hull_dmg = stats.get("ship_hull_damage_add", 0.0) * (1.0 + stats.get("ship_hull_damage_mult", 0.0))
    crew_dmg = stats.get("ship_crew_damage_add", 0.0) * (1.0 + stats.get("ship_crew_damage_mult", 0.0))
    armor = max(0.0, stats.get("ship_armor_add", 0.0) * (1.0 + stats.get("ship_armor_mult", 0.0)))
    speed = max(1.0, stats.get("ship_movement_speed_add", 5.0) * (1.0 + stats.get("ship_movement_speed_mult", 0.0)))
    accuracy = max(0.05, stats.get("ship_accuracy_add", 0.0) * (1.0 + stats.get("ship_accuracy_mult", 0.0)))
    visibility = max(1.0, stats.get("ship_visibility_add", 10.0) * (1.0 + stats.get("ship_visibility_mult", 0.0)))
    detection = max(1.0, stats.get("ship_detection_add", 10.0) * (1.0 + stats.get("ship_detection_mult", 0.0)))
    crit_chance = max(0.0, stats.get("ship_critical_hit_chance_add", 0.0) * (1.0 + stats.get("ship_critical_hit_chance_mult", 0.0)))
    crit_mult = 1.0 + max(0.0, stats.get("ship_critical_hit_multiplier_add", 0.5))
    vulnerability = max(1.0, stats.get("ship_vulnerability_add", 1.0) * (1.0 + stats.get("ship_vulnerability_mult", 0.0)))
    screening = max(0.0, stats.get("ship_screening_add", 0.0) * (1.0 + stats.get("ship_screening_mult", 0.0)))
    readiness = max(1.0, stats.get("ship_readiness_gain_add", 10.0) * (1.0 + stats.get("ship_readiness_gain_mult", 0.0)))
    supply_cap = stats.get("ship_supply_capacity_add", 0.0)
    supply_cost_mult = max(0.1, 1.0 + stats.get("ship_supply_cost_mult", 0.0))
    suffered_acc_mult = stats.get("ship_suffered_accuracy_mult", 0.0)
    suffered_hull_mult = stats.get("ship_suffered_hull_damage_mult", 0.0)
    suffered_crew_mult = stats.get("ship_suffered_crew_damage_mult", 0.0)
    suffered_crit_mult = stats.get("ship_suffered_crit_chance_mult", 0.0)

    vs_acc: Dict[str, float] = {}
    vs_hull: Dict[str, float] = {}
    for k, v in stats.items():
        if k.startswith("ship_battle_against_") and k.endswith("_accuracy_mult"):
            t = k[len("ship_battle_against_"):-len("_accuracy_mult")]
            vs_acc[t] = vs_acc.get(t, 0.0) + v
        elif k.startswith("ship_battle_against_") and k.endswith("_hull_damage_mult"):
            t = k[len("ship_battle_against_"):-len("_hull_damage_mult")]
            vs_hull[t] = vs_hull.get(t, 0.0) + v

    level_mult = mod_cost_factor ** mod_levels

    return ShipSpec(
        ship_id=ship_id,
        group=str(ship_def.get("ship_group", "")),
        cost_progress=float(stats.get("ship_construction_progress_max_add", 5000.0)) * level_mult,
        hp_max=hp_max,
        crew_max=crew_max,
        hull_dmg=hull_dmg,
        crew_dmg=crew_dmg,
        armor=armor,
        speed=speed,
        accuracy=accuracy,
        visibility=visibility,
        detection=detection,
        crit_chance=crit_chance,
        crit_mult=crit_mult,
        vulnerability=vulnerability,
        screening=screening,
        readiness_gain=readiness,
        supply_capacity=supply_cap,
        supply_cost_mult=supply_cost_mult,
        suffered_accuracy_mult=suffered_acc_mult,
        suffered_hull_damage_mult=suffered_hull_mult,
        suffered_crew_damage_mult=suffered_crew_mult,
        suffered_crit_chance_mult=suffered_crit_mult,
        blockade_strength=stats.get("ship_blockade_strength_add", 0.0),
        blockade_mult=1.0 + stats.get("ship_blockade_strength_mult", 0.0),
        power_projection=stats.get("ship_power_projection_add", 0.0),
        mod_levels=mod_levels,
        construction_level_mult=level_mult,
        materiel_goods=materiel,
        construction_goods=constr,
        vs_type_acc_mult=vs_acc,
        vs_type_hull_mult=vs_hull,
        selected_mods=dict(selected_mods),
    )


# =============================================================================
# 3. 6-Step Naval Combat Simulator + REPLACE:naval_battle_size
# =============================================================================

@dataclass
class CombatUnit:
    spec: ShipSpec
    hp: float
    crew: float
    readiness: float = 0.0
    target_weight: float = 1.0
    withdrawn: bool = False

    @property
    def alive(self) -> bool:
        return self.hp > 0 and self.crew > 0 and not self.withdrawn

    @property
    def active(self) -> bool:
        return self.alive and (self.crew / max(self.spec.crew_max, 1.0)) > 0.10


def calc_naval_battle_size(
    own: List[ShipSpec],
    enemy: List[ShipSpec],
    commander_limit: int = 100,
    no_commander_limit: int = 10,
) -> int:
    """Matches zz_naval_overhaul_script_values.txt REPLACE:naval_battle_size."""
    if not own or not enemy:
        return 0
    base_cap = min(len(own), max(no_commander_limit, int(commander_limit * 0.5)))
    own_det = sum(s.detection for s in own) / len(own)
    own_vis = max(sum(s.visibility for s in own) / len(own), 1.0)
    ene_det = max(sum(s.detection for s in enemy) / len(enemy), 1.0)
    ene_vis = sum(s.visibility for s in enemy) / len(enemy)
    ratio = max(0.35, min(2.5, (own_det * ene_vis) / (ene_det * own_vis)))
    recon_add = ratio * len(enemy) * 0.25
    raw_total = int(round(base_cap + recon_add))
    return min(len(own), commander_limit, max(1, raw_total))


def simulate_battle(
    side_a: List[ShipSpec],
    side_b: List[ShipSpec],
    defines: Dict[str, Dict[str, Any]],
    seed: int = 42,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    mil_def = defines.get("NMilitary", {})
    no_cmd_limit = int(mil_def.get("MILITARY_FORMATION_COMMAND_LIMIT_NO_COMMANDER", 10) or 10)
    n_a = calc_naval_battle_size(side_a, side_b, commander_limit=100, no_commander_limit=no_cmd_limit)
    n_b = calc_naval_battle_size(side_b, side_a, commander_limit=100, no_commander_limit=no_cmd_limit)

    w_min = float(mil_def.get("TARGETING_SHIP_WEIGHT_RANDOM_MIN", 0.01) or 0.01)
    w_max = float(mil_def.get("TARGETING_SHIP_WEIGHT_RANDOM_MAX", 1.0) or 1.0)
    units_a = [CombatUnit(s, s.hp_max, s.crew_max, target_weight=rng.uniform(w_min, w_max)) for s in side_a[:n_a]]
    units_b = [CombatUnit(s, s.hp_max, s.crew_max, target_weight=rng.uniform(w_min, w_max)) for s in side_b[:n_b]]

    crit_armor_red = float(mil_def.get("NAVAL_BATTLE_CRIT_ARMOR_REDUCTION", 0.5) or 0.5)
    zero_dmg_thresh = float(mil_def.get("ZERO_DAMAGE_HIT_RATIO_THRESHOLD", 0.5) or 0.5)
    min_zero_hits = int(mil_def.get("MIN_ATTACKS_ZERO_DAMAGE_HIT_PENALTY", 50) or 50)
    zero_desire_add = float(mil_def.get("SHIP_WITHDRAW_DESIRE_HIGH_ZERO_DAMAGE_HIT_RATIO", 0.1) or 0.1)

    hits_tracker = {"a": [0, 0], "b": [0, 0]}  # [total_hits, zero_dmg_hits]

    def step_side(side_key: str, att_list: List[CombatUnit], def_list: List[CombatUnit], day: int) -> None:
        if not def_list:
            return
        tot_vuln = sum(d.spec.vulnerability for d in def_list)
        tot_screen = sum(d.spec.screening for d in def_list)
        screen_ratio = min(tot_screen / max(tot_vuln, 1e-6), 1.0)
        own_pow = sum(u.spec.hull_dmg * 0.75 + u.spec.crew_dmg * 0.25 for u in att_list)
        ene_pow = sum(u.spec.hull_dmg * 0.75 + u.spec.crew_dmg * 0.25 for u in def_list)

        for att in att_list:
            live_defs = [d for d in def_list if d.active]
            if not live_defs:
                break
            att.readiness += att.spec.readiness_gain
            while att.readiness >= 100.0 and att.active:
                live_defs = [d for d in def_list if d.active]
                if not live_defs:
                    break
                att.readiness -= 100.0

                hp_pct = att.hp / max(att.spec.hp_max, 1.0)
                w_desire = 0.40 if hp_pct < 0.25 else (0.10 if hp_pct < 0.50 else (0.025 if hp_pct < 0.80 else 0.0))
                if day >= 5 and (own_pow / max(ene_pow, 1e-6)) < 0.5:
                    w_desire += 0.10 + 0.15 * min((day - 5) / 10.0, 1.0)
                t_hits, z_hits = hits_tracker[side_key]
                if t_hits >= min_zero_hits and (z_hits / t_hits) > zero_dmg_thresh:
                    w_desire += zero_desire_add

                if w_desire > 0 and rng.random() < w_desire:
                    if rng.random() < min(1.0, 0.5 + att.spec.speed * 0.04):
                        att.withdrawn = True
                        break

                weights = []
                for d in live_defs:
                    base_w = d.spec.vulnerability * d.target_weight
                    if d.spec.screening > d.spec.vulnerability:
                        base_w = max(base_w, d.spec.screening * d.target_weight * (1.0 + 9.0 * screen_ratio * 0.9))
                    weights.append(max(base_w, 0.01))
                tgt = rng.choices(live_defs, weights=weights, k=1)[0]

                acc = att.spec.accuracy * (1.0 + att.spec.vs_type_acc_mult.get(tgt.spec.ship_id, 0.0)) * max(0.1, 1.0 + tgt.spec.suffered_accuracy_mult)
                eff_speed = tgt.spec.speed - (tgt.spec.visibility / 15.0)
                miss_chance = max(0.05, min(0.90, 0.5 + 0.03 * (eff_speed - acc * 5.0)))
                if rng.random() < miss_chance:
                    continue

                crit_chance = max(0.0, min(0.95, att.spec.crit_chance * max(0.1, 1.0 + tgt.spec.suffered_crit_chance_mult)))
                is_crit = rng.random() < crit_chance
                eff_armor = tgt.spec.armor * ((1.0 - crit_armor_red) if is_crit else 1.0)
                dmg_mult = att.spec.crit_mult if is_crit else 1.0
                unscreened_extra = 1.0 + (tgt.spec.vulnerability / 100.0) * (1.0 - screen_ratio)
                hull_mult = 1.0 + att.spec.vs_type_hull_mult.get(tgt.spec.ship_id, 0.0)
                crew_factor = max(0.2, att.crew / max(att.spec.crew_max, 1.0))

                raw_hull = att.spec.hull_dmg * hull_mult * dmg_mult * unscreened_extra * crew_factor
                raw_crew = att.spec.crew_dmg * dmg_mult * unscreened_extra * crew_factor

                suffered_hull_mult = max(0.1, 1.0 + tgt.spec.suffered_hull_damage_mult)
                suffered_crew_mult = max(0.1, 1.0 + tgt.spec.suffered_crew_damage_mult)

                # Victoria 3 1.15.1 flat armor subtraction (concept_ship_armor_desc)
                hull_dealt = max(0.0, raw_hull - eff_armor) * suffered_hull_mult
                crew_dealt = max(0.0, raw_crew - eff_armor * 0.5) * suffered_crew_mult

                hits_tracker[side_key][0] += 1
                if hull_dealt <= 0.0:
                    hits_tracker[side_key][1] += 1

                tgt.hp = max(0.0, tgt.hp - hull_dealt)
                tgt.crew = max(0.0, tgt.crew - crew_dealt)

    for day in range(1, 121):
        act_a = [u for u in units_a if u.active]
        act_b = [u for u in units_b if u.active]
        if not act_a or not act_b:
            break
        step_side("a", act_a, act_b, day)
        step_side("b", act_b, act_a, day)

    sunk_a = sum(1 for u in units_a if u.hp <= 0 or u.crew <= 0)
    sunk_b = sum(1 for u in units_b if u.hp <= 0 or u.crew <= 0)
    dmg_a = sum(u.spec.hp_max - u.hp for u in units_a)
    dmg_b = sum(u.spec.hp_max - u.hp for u in units_b)
    cost_lost_a = sum(
        max(1.0, sum(u.spec.construction_goods.values()) * u.spec.construction_level_mult)
        * (1.0 - u.hp / max(u.spec.hp_max, 1.0))
        for u in units_a
    )
    cost_lost_b = sum(
        max(1.0, sum(u.spec.construction_goods.values()) * u.spec.construction_level_mult)
        * (1.0 - u.hp / max(u.spec.hp_max, 1.0))
        for u in units_b
    )
    exchange_a_to_b = cost_lost_b / max(cost_lost_a, 1.0)
    return {
        "n_a": n_a,
        "n_b": n_b,
        "sunk_a": sunk_a,
        "sunk_b": sunk_b,
        "dmg_a": dmg_a,
        "dmg_b": dmg_b,
        "exchange_a_to_b": exchange_a_to_b,
    }


def simulate_battle_avg(side_a: List[ShipSpec], side_b: List[ShipSpec], defines: Dict[str, Dict[str, Any]], runs: int = 40) -> Dict[str, float]:
    res = [simulate_battle(side_a, side_b, defines, seed=100 + i) for i in range(runs)]
    return {
        "n_a": res[0]["n_a"],
        "n_b": res[0]["n_b"],
        "avg_sunk_a": sum(r["sunk_a"] for r in res) / runs,
        "avg_sunk_b": sum(r["sunk_b"] for r in res) / runs,
        "avg_exchange_a_to_b": sum(r["exchange_a_to_b"] for r in res) / runs,
    }


# =============================================================================
# 4. Economy, Bombardment & AI Behavior Simulators
# =============================================================================

def ship_ic_cost(spec: ShipSpec, goods_prices: Dict[str, float]) -> float:
    base = sum(qty * goods_prices.get(g, 40.0) for g, qty in spec.construction_goods.items())
    return base * spec.construction_level_mult


def ship_weekly_materiel_cost(spec: ShipSpec, goods_prices: Dict[str, float]) -> float:
    return sum(qty * goods_prices.get(g, 40.0) for g, qty in spec.materiel_goods.items())


def simulate_bombardment_and_blockade(defines: Dict[str, Dict[str, Any]], days: int = 180) -> Dict[str, float]:
    mil = defines.get("NMilitary", {})
    econ = defines.get("NEconomy", {})
    dev_max = float(mil.get("BOMBARDMENT_DEVASTATION_MAX", 25.0) or 25.0)
    dev_rate = float(mil.get("BOMBARDMENT_DEVASTATION_RATE", 0.20) or 0.20)
    dmg_chance = float(mil.get("BOMBARDMENT_BUILDING_DAMAGE_BASE_CHANCE", 0.02) or 0.02)
    blk_world = float(mil.get("BLOCKADE_WORLD_MARKET_ACCESS_IMPACT_SCALING", 0.75) or 0.75)
    blk_lane = float(mil.get("BLOCKADE_SHIPPING_LANE_IMPACT_SCALING", 0.75) or 0.75)
    shortage_max = float(econ.get("SUPPLY_NETWORK_SHORTAGE_PENALTY_MAX", 0.50) or 0.50)

    devastation = min(dev_max, dev_rate * days)
    expected_building_hits = dmg_chance * days
    return {
        "days": days,
        "devastation": devastation,
        "expected_building_hits": expected_building_hits,
        "blockade_world_market_scaling": blk_world,
        "blockade_shipping_lane_scaling": blk_lane,
        "shortage_penalty_max": shortage_max,
    }


def _nte_scaled_bonus(value: float, threshold: float, divisor: float, cap: float) -> float:
    """`if value > threshold: add min(cap, (value - threshold) / divisor)`."""
    if value <= threshold:
        return 0.0
    return min(cap, (value - threshold) / divisor)


def nte_effective_tonnage(spec: ShipSpec, jeune_ecole: bool = False) -> float:
    """Mirror of Naval Treaty Expanded common/script_values/nte_ship_values.txt."""
    capital_bases = {
        "ship_type_monitor": 10.0,
        "ship_type_ship_of_the_line": 12.0,
        "ship_type_early_ironclad": 18.0,
        "ship_type_modern_ironclad": 24.0,
        "ship_type_pre_dreadnought": 30.0,
        "ship_type_dreadnought": 40.0,
        "ship_type_super_dreadnought": 55.0,
    }
    cruiser_bases = {
        "ship_type_frigate": 3.0,
        "ship_type_iron_frigate": 5.0,
        "ship_type_protected_cruiser": 6.0,
        "ship_type_armored_cruiser": 8.0,
        "ship_type_light_cruiser": 9.0,
        "ship_type_seaplane_tender": 13.0,
        "ship_type_aircraft_carrier": 22.0,
    }
    if spec.ship_id in ("ship_type_early_troop_ship", "ship_type_troop_ship"):
        return 0.0
    if spec.ship_id == "ship_type_coastal_defense_ship":
        # Checked before the capital group in the script, with its own lower scale.
        return round(
            14.0
            + _nte_scaled_bonus(spec.power_projection, 130.0, 30.0, 10.0)
            + _nte_scaled_bonus(spec.hp_max, 1400.0, 300.0, 8.0),
            2,
        )
    if spec.group == "ship_group_capital_ships":
        base = capital_bases.get(spec.ship_id, 20.0)
        tonnage = (
            base
            + _nte_scaled_bonus(spec.power_projection, 150.0, 22.0, 55.0)
            + _nte_scaled_bonus(spec.hp_max, 2000.0, 220.0, 50.0)
        )
        return round(tonnage, 2)
    if spec.group == "ship_group_cruisers":
        base = cruiser_bases.get(spec.ship_id, 6.0)
        tonnage = (
            base
            + _nte_scaled_bonus(spec.power_projection, 120.0, 25.0, 22.0)
            + _nte_scaled_bonus(spec.hp_max, 1200.0, 220.0, 18.0)
        )
        # 10,000t Treaty Cruiser surcharge takes priority over the Jeune Ecole discount.
        if spec.ship_id not in ("ship_type_aircraft_carrier", "ship_type_seaplane_tender") and (
            spec.hp_max >= 3400.0 or spec.power_projection >= 380.0
        ):
            tonnage += 8.0
        elif jeune_ecole:
            tonnage *= 0.72
        return round(tonnage, 2)
    if spec.group == "ship_group_torpedo_craft":
        # Treaty-exempt: 0 combat tonnage (nte_ship_values.txt has no torpedo branch).
        return 0.0
    return 0.0


def resolve_base_ai_complexity(ai_strats: Dict[str, Any]) -> float:
    strat = ai_strats.get("ai_strategy_default", {})
    blk = strat.get("max_ship_design_complexity", {}) if isinstance(strat, dict) else {}
    if not isinstance(blk, dict):
        return 10.0
    val = float(blk.get("value", 10.0) or 10.0)
    adds = blk.get("_injected_adds", [])
    if not isinstance(adds, list):
        adds = [adds]
    for a in adds:
        if isinstance(a, (int, float)):
            val += float(a)
    return val


def ai_pick_mods(
    ship_id: str,
    ship_def: Dict[str, Any],
    mods_db: Dict[str, Dict[str, Any]],
    max_complexity: float = 22.0,
    min_utility_score: float = 1.125,
    market_ratio: float = 1.0,
    doctrine: str = "professional_navy",
) -> Tuple[Dict[str, str], int]:
    """Simulate AI ship designer picking mods under real modification-level complexity budget."""
    pools = get_ship_slot_pools(ship_def)
    chosen: Dict[str, str] = {}
    used_levels = 0

    if market_ratio >= 2.0:
        mkt_mult = 0.1
    elif market_ratio <= 0.75:
        mkt_mult = 1.25
    else:
        mkt_mult = 1.25 * (2.0 - market_ratio) / (2.0 - 0.75)

    active_doctrines: Set[str] = set()
    if doctrine == "professional_navy":
        active_doctrines.update({"ship_mod_capital_doctrine", "ship_mod_power_projection_doctrine"})
    elif doctrine == "jeune_ecole":
        active_doctrines.add("ship_mod_jeune_ecole_doctrine")
    elif doctrine == "merchant_navy":
        active_doctrines.add("ship_mod_merchant_navy_doctrine")
    elif doctrine == "coastal_defence":
        active_doctrines.add("ship_mod_coastal_defence_doctrine")

    def score_mod(mid: str) -> float:
        mdef = mods_db.get(mid, {})
        aw = mdef.get("ai_weight", {})
        base_val = 1.0
        mult_factor = 1.0
        if isinstance(aw, dict):
            v = aw.get("value", 1.0)
            if isinstance(v, (int, float)):
                base_val = float(v)
            for mname in _as_list(aw.get("multiply")):
                if mname == "ship_mod_market_multiplier":
                    mult_factor *= mkt_mult
                elif mname in active_doctrines:
                    mult_factor *= 1.5
                elif mname == "ship_mod_budget_high_mult":
                    mult_factor *= 1.15 if max_complexity >= 19.0 else 0.70
                elif mname == "ship_mod_budget_mid_mult":
                    mult_factor *= 1.05 if max_complexity >= 19.0 else 0.95
                elif mname == "ship_mod_budget_low_mult":
                    mult_factor *= 0.85 if max_complexity >= 19.0 else 1.30
        return base_val * mult_factor

    core_slots = [s for s in pools if not s.startswith("ship_mod_slot_utility") and pools[s]]
    util_slots = [s for s in pools if s.startswith("ship_mod_slot_utility") and pools[s]]

    # First reserve level-1 baseline for every core slot
    for slot_id in core_slots:
        base_mid = pools[slot_id][0]
        chosen[slot_id] = base_mid
        used_levels += compute_mod_level(slot_id, base_mid, ship_def, mods_db)

    # Greedily evaluate upgrades in core slots and additions in utility slots by complexity budget
    candidates_ranked: List[Tuple[float, str, str, int]] = []
    for slot_id in core_slots:
        base_mid = chosen[slot_id]
        base_lvl = compute_mod_level(slot_id, base_mid, ship_def, mods_db)
        base_sc = score_mod(base_mid)
        for mid in pools[slot_id][1:]:
            lvl = compute_mod_level(slot_id, mid, ship_def, mods_db)
            delta_lvl = max(1, lvl - base_lvl)
            sc = score_mod(mid)
            if sc > base_sc:
                candidates_ranked.append(((sc - base_sc) / delta_lvl, slot_id, mid, lvl - base_lvl))

    for slot_id in util_slots:
        best_mid = None
        best_sc = -1.0
        for mid in pools[slot_id]:
            sc = score_mod(mid)
            if sc >= min_utility_score and sc > best_sc:
                best_sc = sc
                best_mid = mid
        if best_mid is not None:
            lvl = compute_mod_level(slot_id, best_mid, ship_def, mods_db)
            candidates_ranked.append((best_sc / max(1, lvl), slot_id, best_mid, lvl))

    candidates_ranked.sort(key=lambda x: x[0], reverse=True)
    for _, slot_id, mid, delta_lvl in candidates_ranked:
        if used_levels + delta_lvl <= max_complexity:
            if slot_id.startswith("ship_mod_slot_utility") and slot_id in chosen:
                continue
            chosen[slot_id] = mid
            used_levels += delta_lvl

    return chosen, used_levels


# =============================================================================
# 5. Main Audit & Reporting
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Victoria 3 Naval Overhaul .txt Simulator")
    parser.add_argument("--vanilla-dir", type=Path, default=DEFAULT_VANILLA_DIR, help="Path to Victoria 3 /game directory")
    parser.add_argument("--kuromi-dir", type=Path, default=DEFAULT_KUROMI_DIR, help="Path to Kuromi AI mod directory")
    parser.add_argument("--nte-dir", type=Path, default=DEFAULT_NTE_DIR, help="Path to Naval Treaty Expanded directory")
    parser.add_argument("--no-kuromi", action="store_true", help="Disable loading Kuromi AI companion mod")
    parser.add_argument("--assert-mode", action="store_true", help="Run regression assertions and exit non-zero on failure")
    args = parser.parse_args()

    roots = []
    if args.vanilla_dir.exists():
        roots.append(args.vanilla_dir)
    if not args.no_kuromi and args.kuromi_dir.exists():
        roots.append(args.kuromi_dir)
    if args.nte_dir.exists():
        roots.append(args.nte_dir)
    roots.append(MOD_DIR)

    warnings: List[str] = []
    global_vars = load_scripted_variables(roots)
    defines = load_defines(roots)
    goods = load_vfs_folder(roots, "common/goods", warnings, global_vars)
    ship_types = load_vfs_folder(roots, "common/ship_types", warnings, global_vars)
    ship_mods = load_vfs_folder(roots, "common/ship_modifications", warnings, global_vars)
    slots = load_vfs_folder(roots, "common/ship_modification_slots", warnings, global_vars)
    ai_strats = load_vfs_folder(roots, "common/ai_strategies", warnings, global_vars)
    script_vals = load_vfs_folder(roots, "common/script_values", warnings, global_vars)
    static_mods = load_vfs_folder(roots, "common/static_modifiers", warnings, global_vars)
    journal_entries = load_vfs_folder(roots, "common/journal_entries", warnings, global_vars)
    mod_events = load_vfs_folder([MOD_DIR], "events", warnings, global_vars)

    goods_prices: Dict[str, float] = {}
    for gname, gdef in goods.items():
        if isinstance(gdef, dict) and isinstance(gdef.get("cost"), (int, float)):
            goods_prices[gname] = float(gdef["cost"])

    loc_zh, dupes_zh = load_localization_with_dupes(MOD_DIR, "simp_chinese")
    loc_en, dupes_en = load_localization_with_dupes(MOD_DIR, "english")

    mil_def = defines.get("NMilitary", {})
    mod_cost_factor = float(mil_def.get("SHIP_CONSTRUCTION_COST_MODIFICATION_LEVEL_FACTOR", 1.028) or 1.028)
    kuromi_util_min = float(defines.get("NAI", {}).get("SHIP_DESIGN_UTILITY_MOD_MIN_SCORE", 1.0) or 1.0)
    base_ai_complexity = resolve_base_ai_complexity(ai_strats)

    print("=== 1. VFS / Compatibility / Localization Audit ===")
    print(f"Loaded ship_types={len(ship_types)}, ship_modifications={len(ship_mods)}, slots={len(slots)}, base_ai_complexity={base_ai_complexity:.1f}, warnings={len(warnings)}")
    for w in warnings[:10]:
        print(f"  WARN: {w}")

    conflict_files = [
        ("common/ai_strategies/00_default_strategy.txt", MOD_DIR / "common/ai_strategies/00_default_strategy.txt"),
        ("common/script_values/command_values.txt", MOD_DIR / "common/script_values/command_values.txt"),
        ("common/naval_mission_types/00_naval_mission_types.txt", MOD_DIR / "common/naval_mission_types/00_naval_mission_types.txt"),
    ]
    active_conflicts = [lbl for lbl, p in conflict_files if p.exists()]
    print(f"Full-file override conflicts present: {len(active_conflicts)} -> {active_conflicts}")

    # Validate modifiers against Vanilla 1.15.1 modifier_type_definitions
    vanilla_mod_defs = load_vanilla_modifier_definitions(args.vanilla_dir)
    unknown_modifiers: List[str] = []
    if vanilla_mod_defs:
        mod_txt_files = list((MOD_DIR / "common").rglob("*.txt"))
        for fp in mod_txt_files:
            for mk in re.findall(r"^\s*((?:ship|country|building|character)_[a-z0-9_]+)\s*=", fp.read_text(encoding="utf-8-sig"), re.M):
                if mk == "ship_group" or mk.startswith(("ship_type_", "ship_mod_", "ship_group_", "ship_veterancy_")):
                    continue
                if mk not in vanilla_mod_defs:
                    unknown_modifiers.append(f"{fp.name}:{mk}")
    print(f"Unknown 1.15.1 modifier keys: {len(unknown_modifiers)} -> {unknown_modifiers}")

    # Check all 22 ship types: required core slots (ship_type.cpp:159), default_modifications, pool validity, utility stacking, supply ship
    required_core_slots = sorted([sl for sl, sdef in slots.items() if isinstance(sdef, dict) and sdef.get("utility") is not True])
    missing_core_slots: List[str] = []
    missing_defaults: List[str] = []
    invalid_defaults: List[str] = []
    negative_supply_defaults: List[Tuple[str, float]] = []
    stackable_utils_by_ship: Dict[str, List[str]] = {}
    specs_default: Dict[str, ShipSpec] = {}
    for sid, sdef in ship_types.items():
        if not isinstance(sdef, dict) or not sid.startswith("ship_type_"):
            continue
        dm = get_default_mods(sdef)
        pools = get_ship_slot_pools(sdef)
        for req_sl in required_core_slots:
            if not pools.get(req_sl):
                missing_core_slots.append(f"{sid}:{req_sl}")
        if not dm:
            missing_defaults.append(sid)
        for sl, mid in dm.items():
            if mid not in pools.get(sl, []):
                invalid_defaults.append(f"{sid}:{sl}={mid}")
        spec = build_ship_spec(sid, sdef, ship_mods, dm, mod_cost_factor)
        specs_default[sid] = spec
        if sid != "ship_type_supply_ship" and spec.supply_capacity <= 10.0:
            negative_supply_defaults.append((sid, spec.supply_capacity))

        util_counts: Dict[str, int] = {}
        for s_idx in range(1, 5):
            for mid in set(pools.get(f"ship_mod_slot_utility_{s_idx}", [])):
                util_counts[mid] = util_counts.get(mid, 0) + 1
        duped_u = sorted([mid for mid, cnt in util_counts.items() if cnt >= 2])
        if duped_u:
            stackable_utils_by_ship[sid] = duped_u

    print(f"Ship types missing/invalid slots or defaults: missing_core={missing_core_slots}, missing_def={len(missing_defaults)}, invalid_def={len(invalid_defaults)}")
    print(f"Utility mods stackable >=2x on ANY ship: {len(stackable_utils_by_ship)} -> {stackable_utils_by_ship}")

    # Comprehensive localization audit
    mod_custom_mods = load_vfs_folder([MOD_DIR], "common/ship_modifications", [])
    mod_static_mods = load_vfs_folder([MOD_DIR], "common/static_modifiers", [])
    mod_jes = load_vfs_folder([MOD_DIR], "common/journal_entries", [])

    required_loc_keys: List[str] = []
    for k in mod_custom_mods.keys():
        required_loc_keys.extend([k, f"{k}_desc"])
    required_loc_keys.extend(["ship_mod_slot_hull", "ship_mod_slot_secondary", "ship_mod_slot_utility_4", "NAVAL_BATTLE_SIZE_RECON_ADVANTAGE"])
    required_loc_keys.extend(mod_static_mods.keys())
    for je_key in mod_jes.keys():
        required_loc_keys.extend([je_key, f"{je_key}_reason"])
    for ev_key, ev_body in mod_events.items():
        if ev_key.startswith("naval_overhaul.") and isinstance(ev_body, dict):
            required_loc_keys.extend([f"{ev_key}.t", f"{ev_key}.d", f"{ev_key}.f"])
            for opt in _as_list(ev_body.get("option")):
                if isinstance(opt, dict) and "name" in opt:
                    required_loc_keys.append(str(opt["name"]))

    missing_zh = [k for k in required_loc_keys if k not in loc_zh]
    missing_en = [k for k in required_loc_keys if k not in loc_en]
    loc_sym_diff = sorted(set(loc_zh.keys()) ^ set(loc_en.keys()))
    print(f"Localization check: dupes_zh={dupes_zh}, dupes_en={dupes_en}, missing_zh={missing_zh}, missing_en={missing_en}, asym={loc_sym_diff}")

    # Check UTF-8 BOM on all mod .txt/.yml/.gui files
    no_bom_files: List[str] = []
    for root_dir, _, fnames in os.walk(MOD_DIR):
        if any(skip in root_dir for skip in (".git", "__pycache__", ".dsh")):
            continue
        for fn in fnames:
            if fn.endswith((".txt", ".yml", ".gui")):
                fp_b = Path(root_dir) / fn
                if not fp_b.read_bytes().startswith(b"\xef\xbb\xbf"):
                    no_bom_files.append(str(fp_b.relative_to(MOD_DIR)))
    print(f"Mod .txt/.yml/.gui files missing UTF-8 BOM: {len(no_bom_files)} -> {no_bom_files}")

    # Tech-tree closure check
    tech_defs = load_vfs_folder([args.vanilla_dir], "common/technology/technologies", [])
    def _tech_closure(seeds: List[str]) -> Set[str]:
        vis, stk = set(seeds), list(seeds)
        while stk:
            cur_t = stk.pop()
            tdef = tech_defs.get(cur_t, {})
            prereqs = tdef.get("unlocking_technologies", []) if isinstance(tdef, dict) else []
            if isinstance(prereqs, str):
                prereqs = [prereqs]
            for pr in prereqs:
                if pr not in vis:
                    vis.add(pr)
                    stk.append(pr)
        return vis

    tech_locked_defaults: List[str] = []
    if tech_defs:
        for sid, sdef in ship_types.items():
            if not isinstance(sdef, dict):
                continue
            st_req = sdef.get("unlocking_technologies", [])
            if isinstance(st_req, str):
                st_req = [st_req]
            clos = _tech_closure([str(x) for x in st_req])
            for sl, mid in get_default_mods(sdef).items():
                mdef = ship_mods.get(mid, {})
                m_req = mdef.get("unlocking_technologies", []) if isinstance(mdef, dict) else []
                if isinstance(m_req, str):
                    m_req = [m_req]
                if not all(str(r) in clos for r in m_req):
                    tech_locked_defaults.append(f"{sid}:{sl}={mid}({m_req})")
    print(f"Tech-locked default_modifications: {len(tech_locked_defaults)} -> {tech_locked_defaults}")

    print("\n=== 2. Tactical 6-Step Combat Matrix ===")
    def make_ship(sid: str, override_mods: Optional[Dict[str, str]] = None) -> ShipSpec:
        sdef = ship_types[sid]
        mods_sel = dict(get_default_mods(sdef))
        if override_mods:
            mods_sel.update(override_mods)
        return build_ship_spec(sid, sdef, ship_mods, mods_sel, mod_cost_factor)

    dn_unscreened = [make_ship("ship_type_dreadnought") for _ in range(4)]
    sub_wolfpack = [make_ship("ship_type_submarine") for _ in range(10)]
    r1 = simulate_battle_avg(dn_unscreened, sub_wolfpack, defines)
    print(f"[Match 1] 4 Dreadnoughts vs 10 Submarines: n=({r1['n_a']},{r1['n_b']}) | sunk=({r1['avg_sunk_a']:.2f},{r1['avg_sunk_b']:.2f}) | Exchange(A->B)={r1['avg_exchange_a_to_b']:.2f}")

    dn_screened = [make_ship("ship_type_dreadnought") for _ in range(3)] + [
        make_ship("ship_type_destroyer", {"ship_mod_slot_utility_1": "utility_mod_sonar_suite"}) for _ in range(6)
    ]
    r2 = simulate_battle_avg(dn_screened, sub_wolfpack, defines)
    print(f"[Match 2] 3 Dreadnoughts + 6 Sonar DD vs 10 Submarines: n=({r2['n_a']},{r2['n_b']}) | sunk=({r2['avg_sunk_a']:.2f},{r2['avg_sunk_b']:.2f}) | Exchange(A->B)={r2['avg_exchange_a_to_b']:.2f}")

    cl_fleet = [make_ship("ship_type_light_cruiser") for _ in range(6)]
    tb_fleet = [make_ship("ship_type_torpedo_boat") for _ in range(12)]
    r3 = simulate_battle_avg(cl_fleet, tb_fleet, defines)
    print(f"[Match 3] 6 Light Cruisers vs 12 Torpedo Boats: n=({r3['n_a']},{r3['n_b']}) | sunk=({r3['avg_sunk_a']:.2f},{r3['avg_sunk_b']:.2f}) | Exchange(A->B)={r3['avg_exchange_a_to_b']:.2f}")

    print("\n=== 3. Economy, Bombardment & NTE Tonnage ===")
    bomb = simulate_bombardment_and_blockade(defines, days=180)
    print(
        f"180d Bombardment: Devastation={bomb['devastation']:.1f}%, Expected Building Hits={bomb['expected_building_hits']:.1f}, "
        f"WorldMarketBlk={bomb['blockade_world_market_scaling']:.2f}, ShortageMax={bomb['shortage_penalty_max']:.2f}"
    )
    for sid in ("ship_type_supply_ship", "ship_type_frigate", "ship_type_dreadnought", "ship_type_light_cruiser", "ship_type_destroyer", "ship_type_submarine", "ship_type_aircraft_carrier"):
        if sid in specs_default:
            sp = specs_default[sid]
            print(f"  {sid:26s} | Lv={sp.mod_levels:2d} | HP={sp.hp_max:6.0f} | Sup={sp.supply_capacity:5.1f} | GoodsCost={ship_ic_cost(sp, goods_prices):8.0f} | NTE_Tons={nte_effective_tonnage(sp):5.1f}")

    print(f"\n=== 4. AI Designer Simulation (base_complexity={base_ai_complexity:.1f}, gp_complexity={base_ai_complexity+4:.1f}, utility_min={kuromi_util_min:.3f}) ===")
    ai_picks: Dict[str, Tuple[Dict[str, str], int]] = {}
    ai_picks_gp: Dict[str, Tuple[Dict[str, str], int]] = {}
    ai_doctrines = {
        "ship_type_dreadnought": "professional_navy",
        "ship_type_destroyer": "coastal_defence",
        "ship_type_submarine": "jeune_ecole",
    }
    for sid, doc in ai_doctrines.items():
        if sid in ship_types:
            picked_norm, lvl_norm = ai_pick_mods(sid, ship_types[sid], ship_mods, max_complexity=base_ai_complexity, min_utility_score=kuromi_util_min, market_ratio=1.0, doctrine=doc)
            picked_gp, lvl_gp = ai_pick_mods(sid, ship_types[sid], ship_mods, max_complexity=base_ai_complexity + 4.0, min_utility_score=kuromi_util_min, market_ratio=1.0, doctrine=doc)
            picked_short, lvl_short = ai_pick_mods(sid, ship_types[sid], ship_mods, max_complexity=base_ai_complexity, min_utility_score=kuromi_util_min, market_ratio=2.2, doctrine=doc)
            ai_picks[sid] = (picked_norm, lvl_norm)
            ai_picks_gp[sid] = (picked_gp, lvl_gp)
            print(f"  {sid:22s} ({doc:17s}) | minor(lv={lvl_norm:2d}): {len(picked_norm):2d} slots | GP(lv={lvl_gp:2d}): {len(picked_gp):2d} slots | shortage(lv={lvl_short:2d}): {len(picked_short):2d} slots")

    if args.assert_mode:
        failures: List[str] = []
        if active_conflicts:
            failures.append(f"Full-file conflicts remain: {active_conflicts}")
        if warnings:
            failures.append(f"VFS merge warnings remain: {warnings}")
        if unknown_modifiers:
            failures.append(f"Unknown 1.15.1 modifier keys: {unknown_modifiers}")
        if missing_core_slots:
            failures.append(f"Ship types missing required core (utility=no) slots (ship_type.cpp:159): {missing_core_slots}")
        if missing_defaults or invalid_defaults:
            failures.append(f"Default modifications errors: missing={missing_defaults}, invalid={invalid_defaults}")
        if negative_supply_defaults:
            failures.append(f"Low/negative supply defaults: {negative_supply_defaults}")
        if stackable_utils_by_ship:
            failures.append(f"Stackable utility mods remain: {stackable_utils_by_ship}")
        if no_bom_files:
            failures.append(f"Files missing UTF-8 BOM: {no_bom_files}")
        if tech_locked_defaults:
            failures.append(f"Tech-locked default_modifications: {tech_locked_defaults}")
        if dupes_zh or dupes_en or missing_zh or missing_en or loc_sym_diff:
            failures.append(
                f"Localization errors: dupes_zh={dupes_zh}, dupes_en={dupes_en}, "
                f"missing_zh={missing_zh}, missing_en={missing_en}, asym={loc_sym_diff}"
            )
        if specs_default.get("ship_type_supply_ship") and specs_default["ship_type_supply_ship"].construction_goods.get("artillery", 0.0) > 0:
            failures.append("Supply ship default consumes artillery!")
        tonnage_by_id = {sid: nte_effective_tonnage(sp) for sid, sp in specs_default.items()}
        for sid in ("ship_type_destroyer", "ship_type_submarine", "ship_type_torpedo_boat"):
            actual = tonnage_by_id[sid]
            if actual != 0:
                failures.append(f"NTE tonnage for {sid}: treaty-exempt, expected 0, actual {actual:.2f}")
        for sid in ("ship_type_early_troop_ship", "ship_type_troop_ship"):
            actual = tonnage_by_id[sid]
            if actual != 0:
                failures.append(f"NTE tonnage for {sid}: expected 0, actual {actual:.2f}")
        cap_t = tonnage_by_id["ship_type_dreadnought"]
        cru_t = tonnage_by_id["ship_type_light_cruiser"]
        if not cap_t > cru_t > 0:
            failures.append(
                f"NTE tonnage ordering: expected capital > cruiser > 0, "
                f"actual dreadnought={cap_t:.2f}, light_cruiser={cru_t:.2f}"
            )
        carrier_t = tonnage_by_id["ship_type_aircraft_carrier"]
        if carrier_t <= 0:
            failures.append(f"NTE tonnage for ship_type_aircraft_carrier: expected > 0, actual {carrier_t:.2f}")
        negative_t = sorted(sid for sid, t in tonnage_by_id.items() if t < 0)
        if negative_t:
            failures.append(f"NTE tonnage negative for: {negative_t}")
        if r1["avg_exchange_a_to_b"] >= 0.90:
            failures.append(f"Match 1 failed: unscreened DN vs Subs exchange={r1['avg_exchange_a_to_b']:.2f} (expected < 0.90)")
        if r2["avg_exchange_a_to_b"] <= 1.35:
            failures.append(f"Match 2 failed: screened DN+DD vs Subs exchange={r2['avg_exchange_a_to_b']:.2f} (expected > 1.35)")
        if r3["avg_exchange_a_to_b"] <= 1.30:
            failures.append(f"Match 3 failed: CL vs TB exchange={r3['avg_exchange_a_to_b']:.2f} (expected > 1.30)")
        if bomb["expected_building_hits"] > 6.5:
            failures.append(f"180d bombardment building hits too high: {bomb['expected_building_hits']:.1f}")
        if base_ai_complexity < 16.0:
            failures.append(f"AI base max_ship_design_complexity={base_ai_complexity:.1f} < 16.0")
        for sid, (pk, lv) in ai_picks.items():
            if len(pk) < 6 or lv > base_ai_complexity:
                failures.append(f"AI designer anomaly for {sid} (minor): slots={len(pk)}<6, lv={lv}/{base_ai_complexity}")
        for sid, (pk, lv) in ai_picks_gp.items():
            if len(pk) < 7 or lv > base_ai_complexity + 4.0:
                failures.append(f"AI designer anomaly for {sid} (GP): slots={len(pk)}<7, lv={lv}/{base_ai_complexity+4.0}")
        if specs_default["ship_type_destroyer"].hp_max >= specs_default["ship_type_light_cruiser"].hp_max:
            failures.append(f"Destroyer HP ({specs_default['ship_type_destroyer'].hp_max:.0f}) >= Light Cruiser HP ({specs_default['ship_type_light_cruiser'].hp_max:.0f})")
        if failures:
            print("\n[FAIL] REGRESSION ASSERTIONS FAILED:")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("\n[PASS] ALL REGRESSION ASSERTIONS PASSED!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
