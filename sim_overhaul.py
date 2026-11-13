#!/usr/bin/env python3
"""
Victoria 3 Naval Overhaul — .txt-Driven VFS & Simulation Tool
Zero external dependencies (Python 3 stdlib only).
Directly parses Vanilla + Mod + Kuromi's AI + Naval Treaty Expanded .txt/.yml files.
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
from typing import Any, Dict, List, Optional, Tuple

VANILLA_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game")
MOD_DIR = Path(__file__).resolve().parent
KUROMI_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\workshop\content\529340\3227982912")
NTE_DIR = Path(r"C:\Users\RedAndBlack\Documents\Paradox Interactive\Victoria 3\mod\Naval Treaty Expanded")


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
    if vars_map is None:
        vars_map = {}

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
                    val = _to_scalar(tokens[pos], vars_map)
                    pos += 1
                else:
                    val = None
                if key.startswith("@") and op == "=" and not isinstance(val, (dict, list)):
                    vars_map[key] = val
                else:
                    items.append((key, op, val))
            else:
                bare_list.append(_to_scalar(tok, vars_map))
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
        # Mixed block (rare, e.g. script_values or triggers)
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


def deep_inject(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    """Jomini INJECT / TRY_INJECT semantics: containers merge/append, scalars/script_values replace."""
    for k, v in src.items():
        if k not in dst:
            dst[k] = v
        elif isinstance(dst[k], dict) and isinstance(v, dict):
            if k in ("modifier", "ai_weight", "potential", "possible", "unlocking_technologies"):
                if k == "modifier":
                    for mk, mv in v.items():
                        if isinstance(mv, (int, float)) and isinstance(dst[k].get(mk), (int, float)):
                            dst[k][mk] = dst[k][mk] + mv
                        else:
                            dst[k][mk] = mv
                else:
                    dst[k] = v
            else:
                deep_inject(dst[k], v)
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
                    deep_inject(base[target], val)
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


def load_vfs_folder(roots: List[Path], rel_folder: str, warnings: List[str]) -> Dict[str, Any]:
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
        parsed = parse_clausewitz(text)
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


def load_localization(root: Path, lang: str) -> Dict[str, str]:
    loc: Dict[str, str] = {}
    folder = root / "localization" / lang
    if not folder.exists():
        return loc
    pat = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"((?:\\.|[^"\\])*)"')
    for f in sorted(folder.glob("*.yml")):
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            m = pat.match(line)
            if m:
                loc[m.group(1)] = m.group(2)
    return loc


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
    blockade_strength: float
    blockade_mult: float
    convoy_raid_mult: float
    power_projection: float
    total_mod_cost: float
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


def build_ship_spec(
    ship_id: str,
    ship_def: Dict[str, Any],
    mods_db: Dict[str, Dict[str, Any]],
    selected_mods: Dict[str, str],
) -> ShipSpec:
    stats: Dict[str, float] = {}
    _sum_mod(stats, ship_def.get("modifier", {}))

    materiel: Dict[str, float] = {}
    constr: Dict[str, float] = {}
    _sum_goods(materiel, ship_def.get("materiel_goods", {}))
    _sum_goods(constr, ship_def.get("construction_goods", {}))

    total_mod_cost = 0.0
    for slot_id, mod_id in selected_mods.items():
        mdef = mods_db.get(mod_id)
        if not isinstance(mdef, dict):
            continue
        _sum_mod(stats, mdef.get("modifier", {}))
        _sum_goods(materiel, mdef.get("materiel_goods", {}))
        _sum_goods(constr, mdef.get("construction_goods", {}))
        total_mod_cost += float(mdef.get("cost", 0.0) or 0.0)

    # Multipliers
    hp_max = stats.get("ship_hit_points_max_add", 100.0) * (1.0 + stats.get("ship_hit_points_max_mult", 0.0))
    crew_max = stats.get("ship_crew_max_add", 100.0) * (1.0 + stats.get("ship_crew_max_mult", 0.0))
    hull_dmg = stats.get("ship_hull_damage_add", 0.0) * (1.0 + stats.get("ship_hull_damage_mult", 0.0))
    crew_dmg = stats.get("ship_crew_damage_add", 0.0) * (1.0 + stats.get("ship_crew_damage_mult", 0.0))
    armor = max(0.0, stats.get("ship_armor_add", 0.0) * (1.0 + stats.get("ship_armor_mult", 0.0)))
    speed = max(1.0, stats.get("ship_movement_speed_add", 5.0) * (1.0 + stats.get("ship_movement_speed_mult", 0.0)))
    accuracy = max(0.05, (stats.get("ship_accuracy_add", 0.0) / 100.0) * (1.0 + stats.get("ship_accuracy_mult", 0.0)))
    visibility = max(1.0, stats.get("ship_visibility_add", 10.0) * (1.0 + stats.get("ship_visibility_mult", 0.0)))
    detection = max(1.0, stats.get("ship_detection_add", 10.0) * (1.0 + stats.get("ship_detection_mult", 0.0)))
    crit_chance = max(0.0, stats.get("ship_critical_hit_chance_add", 0.0) + stats.get("ship_critical_hit_chance_mult", 0.0))
    crit_mult = 1.0 + max(0.0, stats.get("ship_critical_hit_multiplier_add", 0.5))
    vulnerability = max(1.0, stats.get("ship_vulnerability_add", 1.0) * (1.0 + stats.get("ship_vulnerability_mult", 0.0)))
    screening = max(0.0, stats.get("ship_screening_add", 0.0) * (1.0 + stats.get("ship_screening_mult", 0.0)))
    readiness = max(1.0, stats.get("ship_readiness_gain_add", 10.0) * (1.0 + stats.get("ship_readiness_gain_mult", 0.0)))
    supply_cap = stats.get("ship_supply_capacity_add", 0.0)
    supply_cost_mult = max(0.1, 1.0 + stats.get("ship_supply_cost_mult", 0.0))
    suffered_acc_mult = stats.get("ship_suffered_accuracy_mult", 0.0)

    vs_acc: Dict[str, float] = {}
    vs_hull: Dict[str, float] = {}
    for k, v in stats.items():
        if k.startswith("ship_battle_against_") and k.endswith("_accuracy_mult"):
            t = k[len("ship_battle_against_"):-len("_accuracy_mult")]
            vs_acc[t] = vs_acc.get(t, 0.0) + v
        elif k.startswith("ship_battle_against_") and k.endswith("_hull_damage_mult"):
            t = k[len("ship_battle_against_"):-len("_hull_damage_mult")]
            vs_hull[t] = vs_hull.get(t, 0.0) + v

    return ShipSpec(
        ship_id=ship_id,
        group=str(ship_def.get("ship_group", "")),
        cost_progress=float(stats.get("ship_construction_progress_max_add", 5000.0)),
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
        blockade_strength=stats.get("ship_blockade_strength_add", 0.0),
        blockade_mult=1.0 + stats.get("ship_blockade_strength_mult", 0.0),
        convoy_raid_mult=1.0 + stats.get("ship_convoy_raiding_strength_mult", 0.0),
        power_projection=stats.get("ship_power_projection_add", 0.0),
        total_mod_cost=total_mod_cost,
        materiel_goods=materiel,
        construction_goods=constr,
        vs_type_acc_mult=vs_acc,
        vs_type_hull_mult=vs_hull,
        selected_mods=dict(selected_mods),
    )


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


def calc_naval_battle_size(own: List[ShipSpec], enemy: List[ShipSpec]) -> int:
    if not own or not enemy:
        return 0
    own_det = sum(s.detection for s in own) / len(own)
    own_vis = max(sum(s.visibility for s in own) / len(own), 1.0)
    ene_det = max(sum(s.detection for s in enemy) / len(enemy), 1.0)
    ene_vis = sum(s.visibility for s in enemy) / len(enemy)
    ratio = max(0.35, min(2.5, (own_det * ene_vis) / (ene_det * own_vis)))
    raw = ratio * len(enemy) * 0.25
    guaranteed = math.ceil(len(own) * 0.5)
    return min(len(own), max(guaranteed, int(round(raw))))


def simulate_battle(
    side_a: List[ShipSpec],
    side_b: List[ShipSpec],
    defines: Dict[str, Dict[str, Any]],
    seed: int = 42,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    n_a = calc_naval_battle_size(side_a, side_b)
    n_b = calc_naval_battle_size(side_b, side_a)
    units_a = [CombatUnit(s, s.hp_max, s.crew_max, target_weight=rng.uniform(0.1, 1.0)) for s in side_a[:n_a]]
    units_b = [CombatUnit(s, s.hp_max, s.crew_max, target_weight=rng.uniform(0.1, 1.0)) for s in side_b[:n_b]]

    mil_def = defines.get("NMilitary", {})
    round_dur = float(mil_def.get("NAVAL_BATTLE_ROUND_DURATION", 10) or 10)
    armor_div = float(mil_def.get("NAVAL_ARMOR_MITIGATION_DIVISOR", 150) or 150)

    def step_side(att_list: List[CombatUnit], def_list: List[CombatUnit], day: int) -> None:
        if not def_list:
            return
        tot_vuln = sum(d.spec.vulnerability for d in def_list)
        tot_screen = sum(d.spec.screening for d in def_list)
        screen_ratio = min(tot_screen / max(tot_vuln, 1e-6), 1.0)
        own_pow = sum(u.spec.hull_dmg + 0.3 * u.spec.crew_dmg for u in att_list)
        ene_pow = sum(u.spec.hull_dmg + 0.3 * u.spec.crew_dmg for u in def_list)

        for att in att_list:
            live_defs = [d for d in def_list if d.active]
            if not live_defs:
                break
            att.readiness += att.spec.readiness_gain * (10.0 / max(round_dur, 1.0))
            while att.readiness >= 100.0 and att.active:
                live_defs = [d for d in def_list if d.active]
                if not live_defs:
                    break
                att.readiness -= 100.0

                hp_pct = att.hp / max(att.spec.hp_max, 1.0)
                w_desire = 0.40 if hp_pct < 0.25 else (0.10 if hp_pct < 0.50 else (0.025 if hp_pct < 0.80 else 0.0))
                if day >= 5 and (own_pow / max(ene_pow, 1e-6)) < 0.5:
                    w_desire += 0.10 + 0.15 * min((day - 5) / 10.0, 1.0)
                if w_desire > 0 and rng.random() < w_desire:
                    if rng.random() < min(1.0, 0.45 + att.spec.speed * 0.04):
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

                is_crit = rng.random() < att.spec.crit_chance
                eff_armor = tgt.spec.armor * (0.5 if is_crit else 1.0)
                dmg_mult = att.spec.crit_mult if is_crit else 1.0
                unscreened_extra = 1.0 + (tgt.spec.vulnerability / 100.0) * (1.0 - screen_ratio)
                hull_mult = 1.0 + att.spec.vs_type_hull_mult.get(tgt.spec.ship_id, 0.0)
                crew_factor = max(0.2, att.crew / max(att.spec.crew_max, 1.0))

                raw_hull = att.spec.hull_dmg * hull_mult * dmg_mult * unscreened_extra * crew_factor
                raw_crew = att.spec.crew_dmg * dmg_mult * unscreened_extra * crew_factor
                armor_mit = eff_armor / (eff_armor + armor_div)
                tgt.hp = max(0.0, tgt.hp - raw_hull * (1.0 - armor_mit))
                tgt.crew = max(0.0, tgt.crew - raw_crew * (1.0 - armor_mit * 0.5))

    for day in range(1, 121):
        act_a = [u for u in units_a if u.active]
        act_b = [u for u in units_b if u.active]
        if not act_a or not act_b:
            break
        step_side(act_a, act_b, day)
        step_side(act_b, act_a, day)

    sunk_a = sum(1 for u in units_a if u.hp <= 0 or u.crew <= 0)
    sunk_b = sum(1 for u in units_b if u.hp <= 0 or u.crew <= 0)
    dmg_a = sum(u.spec.hp_max - u.hp for u in units_a)
    dmg_b = sum(u.spec.hp_max - u.hp for u in units_b)
    cost_lost_a = sum(max(1.0, sum(u.spec.construction_goods.values())) * (1.0 - u.hp / max(u.spec.hp_max, 1.0)) for u in units_a)
    cost_lost_b = sum(max(1.0, sum(u.spec.construction_goods.values())) * (1.0 - u.hp / max(u.spec.hp_max, 1.0)) for u in units_b)
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
    return sum(qty * goods_prices.get(g, 40.0) for g, qty in spec.construction_goods.items())


def ship_weekly_materiel_cost(spec: ShipSpec, goods_prices: Dict[str, float]) -> float:
    return sum(qty * goods_prices.get(g, 40.0) for g, qty in spec.materiel_goods.items())


def simulate_bombardment_and_blockade(defines: Dict[str, Dict[str, Any]], days: int = 180) -> Dict[str, float]:
    mil = defines.get("NMilitary", {})
    dev_max = float(mil.get("BOMBARDMENT_DEVASTATION_MAX", 25.0) or 25.0)
    dev_rate = float(mil.get("BOMBARDMENT_DEVASTATION_RATE", 0.20) or 0.20)
    dmg_chance = float(mil.get("BOMBARDMENT_BUILDING_DAMAGE_BASE_CHANCE", 0.02) or 0.02)
    blk_supply = float(mil.get("BLOCKADE_SUPPLY_NETWORK_IMPACT_SCALING", 0.75) or 0.75)
    shortage_max = float(mil.get("SUPPLY_NETWORK_SHORTAGE_PENALTY_MAX", 0.50) or 0.50)

    devastation = min(dev_max, dev_rate * days)
    expected_building_hits = dmg_chance * days
    return {
        "days": days,
        "devastation": devastation,
        "expected_building_hits": expected_building_hits,
        "blockade_supply_scaling": blk_supply,
        "shortage_penalty_max": shortage_max,
    }


def nte_effective_tonnage(spec: ShipSpec) -> float:
    if spec.group == "ship_group_capital_ships":
        base = 25.0
        pp_bonus = min(25.0, max(0.0, spec.power_projection - 150.0) * 0.2)
        hp_bonus = min(20.0, max(0.0, spec.hp_max - 2000.0) * 0.01)
        return base + pp_bonus + hp_bonus
    if spec.group == "ship_group_cruisers":
        base = 10.0
        pp_bonus = min(10.0, max(0.0, spec.power_projection - 120.0) * 0.15)
        hp_bonus = min(8.0, max(0.0, spec.hp_max - 1200.0) * 0.01)
        return base + pp_bonus + hp_bonus
    return 0.0


def ai_pick_mods(
    ship_id: str,
    ship_def: Dict[str, Any],
    mods_db: Dict[str, Dict[str, Any]],
    max_complexity: float = 20.0,
    min_utility_score: float = 1.125,
    market_ratio: float = 1.0,
) -> Tuple[Dict[str, str], float]:
    """Simulate AI ship designer picking mods under complexity budget & Kuromi utility min score."""
    pools = get_ship_slot_pools(ship_def)
    chosen: Dict[str, str] = {}
    used_cost = 0.0

    # Market multiplier matching ai_script_values.txt:689
    if market_ratio >= 2.0:
        mkt_mult = 0.1
    elif market_ratio <= 0.75:
        mkt_mult = 1.25
    else:
        mkt_mult = 1.25 * (2.0 - market_ratio) / (2.0 - 0.75)

    for slot_id, candidates in pools.items():
        if not candidates:
            continue
        is_util = slot_id.startswith("ship_mod_slot_utility")
        best_mod = None
        best_score = -1.0
        for mid in candidates:
            mdef = mods_db.get(mid, {})
            cost = float(mdef.get("cost", 0.0) or 0.0)
            if used_cost + cost > max_complexity and best_mod is not None:
                continue
            aw = mdef.get("ai_weight", {})
            base_val = 1.0
            has_mkt = False
            if isinstance(aw, dict):
                v = aw.get("value", 1.0)
                if isinstance(v, (int, float)):
                    base_val = float(v)
                mults = _as_list(aw.get("multiply"))
                if "ship_mod_market_multiplier" in mults:
                    has_mkt = True
            score = base_val * (mkt_mult if has_mkt else 1.0)
            if is_util and score < min_utility_score:
                continue
            if score > best_score:
                best_score = score
                best_mod = mid
        if best_mod is not None:
            chosen[slot_id] = best_mod
            used_cost += float(mods_db.get(best_mod, {}).get("cost", 0.0) or 0.0)
    return chosen, used_cost


# =============================================================================
# 5. Main Audit & Reporting
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Victoria 3 Naval Overhaul .txt Simulator")
    parser.add_argument("--with-kuromi", action="store_true", default=True)
    parser.add_argument("--assert-mode", action="store_true", help="Run regression assertions and exit non-zero on failure")
    args = parser.parse_args()

    roots = [VANILLA_DIR]
    if args.with_kuromi and KUROMI_DIR.exists():
        roots.append(KUROMI_DIR)
    if NTE_DIR.exists():
        roots.append(NTE_DIR)
    roots.append(MOD_DIR)

    warnings: List[str] = []
    defines = load_defines(roots)
    goods = load_vfs_folder(roots, "common/goods", warnings)
    ship_types = load_vfs_folder(roots, "common/ship_types", warnings)
    ship_mods = load_vfs_folder(roots, "common/ship_modifications", warnings)
    slots = load_vfs_folder(roots, "common/ship_modification_slots", warnings)
    ai_strats = load_vfs_folder(roots, "common/ai_strategies", warnings)
    script_vals = load_vfs_folder(roots, "common/script_values", warnings)
    laws = load_vfs_folder(roots, "common/laws", warnings)
    missions = load_vfs_folder(roots, "common/naval_mission_types", warnings)

    goods_prices: Dict[str, float] = {}
    for gname, gdef in goods.items():
        if isinstance(gdef, dict) and isinstance(gdef.get("cost"), (int, float)):
            goods_prices[gname] = float(gdef["cost"])

    loc_zh = load_localization(MOD_DIR, "simp_chinese")
    loc_en = load_localization(MOD_DIR, "english")

    mil_def = defines.get("NMilitary", {})
    mod_cost_factor = float(mil_def.get("SHIP_CONSTRUCTION_COST_MODIFICATION_LEVEL_FACTOR", 1.05) or 1.05)
    kuromi_util_min = float(defines.get("NAI", {}).get("SHIP_DESIGN_UTILITY_MOD_MIN_SCORE", 1.0) or 1.0)

    print("=== 1. VFS / Compatibility / Localization Audit ===")
    print(f"Loaded ship_types={len(ship_types)}, ship_modifications={len(ship_mods)}, slots={len(slots)}, warnings={len(warnings)}")
    for w in warnings[:10]:
        print(f"  WARN: {w}")

    # Check override conflicts
    conflict_files = [
        ("common/ai_strategies/00_default_strategy.txt", MOD_DIR / "common/ai_strategies/00_default_strategy.txt"),
        ("common/script_values/command_values.txt", MOD_DIR / "common/script_values/command_values.txt"),
        ("common/naval_mission_types/00_naval_mission_types.txt", MOD_DIR / "common/naval_mission_types/00_naval_mission_types.txt"),
    ]
    active_conflicts = [lbl for lbl, p in conflict_files if p.exists()]
    print(f"Full-file override conflicts present: {len(active_conflicts)} -> {active_conflicts}")

    # Check default_modifications & supply capacity
    missing_defaults: List[str] = []
    negative_supply_defaults: List[Tuple[str, float]] = []
    specs_default: Dict[str, ShipSpec] = {}
    for sid, sdef in ship_types.items():
        if not isinstance(sdef, dict) or not sid.startswith("ship_type_"):
            continue
        dm = get_default_mods(sdef)
        if not dm:
            missing_defaults.append(sid)
        spec = build_ship_spec(sid, sdef, ship_mods, dm)
        specs_default[sid] = spec
        if spec.supply_capacity <= 10.0:
            negative_supply_defaults.append((sid, spec.supply_capacity))

    print(f"Ship types missing default_modifications: {len(missing_defaults)} -> {missing_defaults[:8]}{'...' if len(missing_defaults) > 8 else ''}")
    print(f"Default ships with supply_capacity <= 10: {negative_supply_defaults}")

    # Check utility stacking exploit (any mod appearing in 2+ utility slots on Dreadnought)
    dn_pools = get_ship_slot_pools(ship_types.get("ship_type_dreadnought", {}))
    slot_counts: Dict[str, int] = {}
    for s_idx in range(1, 5):
        for mid in set(dn_pools.get(f"ship_mod_slot_utility_{s_idx}", [])):
            slot_counts[mid] = slot_counts.get(mid, 0) + 1
    common_u = sorted([mid for mid, cnt in slot_counts.items() if cnt >= 2])
    print(f"Utility mods stackable >=2x on Dreadnought: {len(common_u)} -> {common_u[:8]}{'...' if len(common_u) > 8 else ''}")

    # Check localization gaps for mod-defined modifications
    mod_keys = [k for k in ship_mods.keys() if k.startswith(("ship_mod_hull_", "ship_mod_secondary_", "utility_mod_")) and k not in load_vfs_folder([VANILLA_DIR], "common/ship_modifications", [])]
    missing_zh = [k for k in mod_keys if k not in loc_zh]
    missing_en = [k for k in mod_keys if k not in loc_en]
    print(f"Mod custom modification loc missing: zh={missing_zh}, en={missing_en}")


    # Check UTF-8 BOM on all mod .txt/.yml files & tech-tree validity of default_modifications
    no_bom_files = []
    for root_dir, _, fnames in os.walk(MOD_DIR):
        if any(skip in root_dir for skip in ('.git', '__pycache__', '.dsh-')):
            continue
        for fn in fnames:
            if fn.endswith(('.txt', '.yml')):
                fp_b = Path(root_dir) / fn
                raw_b = fp_b.read_bytes()
                if not raw_b.startswith(b'\xef\xbb\xbf'):
                    no_bom_files.append(str(fp_b.relative_to(MOD_DIR)))
    print(f"Mod .txt/.yml files missing UTF-8 BOM: {len(no_bom_files)} -> {no_bom_files}")

    tech_defs = load_vfs_folder([VANILLA_DIR], "common/technology/technologies", [])
    def _tech_closure(seeds):
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

    tech_locked_defaults = []
    for sid, sdef in ship_types.items():
        st_req = sdef.get("unlocking_technologies", [])
        if isinstance(st_req, str):
            st_req = [st_req]
        clos = _tech_closure(st_req)
        for sl, mid in get_default_mods(sdef).items():
            mdef = ship_mods.get(mid, {})
            m_req = mdef.get("unlocking_technologies", []) if isinstance(mdef, dict) else []
            if isinstance(m_req, str):
                m_req = [m_req]
            if not all(r in clos for r in m_req):
                tech_locked_defaults.append(f"{sid}:{sl}={mid}({m_req})")
    print(f"Tech-locked default_modifications: {len(tech_locked_defaults)} -> {tech_locked_defaults}")

    print("\n=== 2. Tactical 6-Step Combat Matrix ===")
    # Helper to build test ships
    def make_ship(sid: str, override_mods: Optional[Dict[str, str]] = None) -> ShipSpec:
        sdef = ship_types[sid]
        mods_sel = dict(get_default_mods(sdef))
        if override_mods:
            mods_sel.update(override_mods)
        return build_ship_spec(sid, sdef, ship_mods, mods_sel)

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
    print(f"180d Bombardment: Devastation={bomb['devastation']:.1f}%, Expected Building Hits={bomb['expected_building_hits']:.1f}, Blockade Supply Scaling={bomb['blockade_supply_scaling']:.2f}")
    for sid in ("ship_type_frigate", "ship_type_dreadnought", "ship_type_light_cruiser", "ship_type_destroyer", "ship_type_submarine", "ship_type_aircraft_carrier"):
        if sid in specs_default:
            sp = specs_default[sid]
            print(f"  {sid:26s} | HP={sp.hp_max:6.0f} | Sup={sp.supply_capacity:5.1f} | GoodsCost={ship_ic_cost(sp, goods_prices):8.0f} | WkMat={ship_weekly_materiel_cost(sp, goods_prices):6.0f} | NTE_Tons={nte_effective_tonnage(sp):5.1f}")

    print("\n=== 4. AI Designer Simulation (Kuromi threshold = {:.3f}) ===".format(kuromi_util_min))
    for sid in ("ship_type_dreadnought", "ship_type_destroyer", "ship_type_submarine"):
        if sid in ship_types:
            picked_norm, cost_norm = ai_pick_mods(sid, ship_types[sid], ship_mods, max_complexity=20.0, min_utility_score=kuromi_util_min, market_ratio=1.0)
            picked_short, cost_short = ai_pick_mods(sid, ship_types[sid], ship_mods, max_complexity=20.0, min_utility_score=kuromi_util_min, market_ratio=2.2)
            print(f"  {sid:22s} | normal_mkt(cost={cost_norm:.1f}): {len(picked_norm)} slots | shortage_mkt(cost={cost_short:.1f}): {len(picked_short)} slots")

    if args.assert_mode:
        failures: List[str] = []
        if active_conflicts:
            failures.append(f"Full-file conflicts remain: {active_conflicts}")
        if missing_defaults:
            failures.append(f"Missing default_modifications: {missing_defaults}")
        if negative_supply_defaults:
            failures.append(f"Low/negative supply defaults: {negative_supply_defaults}")
        if common_u:
            failures.append(f"4x stackable utility mods remain: {common_u}")
        if no_bom_files:
            failures.append(f"Files missing UTF-8 BOM: {no_bom_files}")
        if tech_locked_defaults:
            failures.append(f"Tech-locked default_modifications: {tech_locked_defaults}")
        if missing_zh or missing_en:
            failures.append(f"Missing loc keys zh={missing_zh}, en={missing_en}")
        if r1["avg_exchange_a_to_b"] >= 0.85:
            failures.append(f"Match 1 failed: unscreened DN vs Subs exchange={r1['avg_exchange_a_to_b']:.2f} (expected < 0.85)")
        if r2["avg_exchange_a_to_b"] <= 1.35:
            failures.append(f"Match 2 failed: screened DN+DD vs Subs exchange={r2['avg_exchange_a_to_b']:.2f} (expected > 1.35)")
        if r3["avg_exchange_a_to_b"] <= 1.30:
            failures.append(f"Match 3 failed: CL vs TB exchange={r3['avg_exchange_a_to_b']:.2f} (expected > 1.30)")
        if bomb["expected_building_hits"] > 6.5:
            failures.append(f"180d bombardment building hits too high: {bomb['expected_building_hits']:.1f}")
        dd_def = get_default_mods(ship_types["ship_type_destroyer"])
        if dd_def.get("ship_mod_slot_hull") != "ship_mod_hull_lightweight":
            failures.append(f"Destroyer default hull={dd_def.get('ship_mod_slot_hull')} (expected ship_mod_hull_lightweight)")
        if "ship_mod_hull_reinforced" in ship_types["ship_type_destroyer"].get("modifications", {}).get("ship_mod_slot_hull", []):
            failures.append("Destroyer hull pool should not include ship_mod_hull_reinforced")
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
