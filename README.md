# Iron & Steam: Naval Overhaul (v0.1.0 — Early Demo)

> **Status: Early Demo (`v0.1.0`)**  
> This mod is in active early development. Core mechanics and automated simulation tests are working, while long-campaign AI fleet composition, late-game pacing, and flavor events are actively being tuned. Contributions, balance reports, and pull requests are very welcome!

A comprehensive naval warfare overhaul for **Victoria 3 (`1.15.*`)** that reworks naval detection, battle size scaling, ship customization (10-slot Ship Designer), convoy raiding, blockades, and strategic sea power.

---

## Features in This Demo

- **Detection & Visibility-Based Battle Size** (`common/script_values/zz_naval_overhaul_script_values.txt`)
  - Uses `REPLACE:naval_battle_size` to scale engagement size dynamically from fleet Detection vs. Visibility (`[0.35x, 2.5x]`) alongside command capacity.
- **10-Slot Ship Designer & 4-Pole Counter Loop** (`common/ship_modification_slots/`, `common/ship_types/`, `common/ship_modifications/`, `gui/ship_designer_popup.gui`)
  - **6 Core Slots**: Hull, Armor, Main Guns, Secondary Armament, Propulsion, Range.
  - **4 Functional Utility Slots**: Sensors/Fire Control (`utility_1`), Survivability/Damage Control (`utility_2`), Special Armament/AA/ASW (`utility_3`), and Endurance/Ops (`utility_4`).
  - Anti-stacking pools, trade-offs in visibility/supply/goods, and tech-validated `default_modifications` across all 22 ship types.
- **Strategic Naval Warfare & Laws/Missions** (`common/defines/`, `common/laws/`, `common/naval_mission_types/`, `common/ai_strategies/`)
  - Uses `TRY_INJECT:` and `INJECT:` for high compatibility with companion mods such as **Naval Treaty Expanded** and AI mods.
- **Bilingual Localization & Multiplayer Sync**
  - Full English and 简体中文 localization (`UTF-8 BOM`), `multiplayer_synchronized = true`.

---

## Contributing

We warmly welcome contributors—whether you want to help with **balance tuning, AI testing, GUI polish, flavor events, compatibility patches, or localization**!

### Local Validation Tooling

The repository includes an offline `.txt`-driven simulator and regression suite (`sim_overhaul.py`) that checks VFS conflicts, UTF-8 BOM encoding, localization coverage, tech-tree closure for `default_modifications`, 6-step naval combat balance, and AI designer picks:

```bash
python sim_overhaul.py --assert-mode
```

### Development Guidelines

Please check `AGENTS.md` and `plan.md` before submitting PRs:
- Keep `.txt` and `.yml` files encoded in **UTF-8 with BOM**.
- Prefer `INJECT:` / `TRY_INJECT:` / `REPLACE:` over full-file overrides wherever the engine supports it.
- Keep `.metadata/metadata.json` with `"multiplayer_synchronized" : true`.
- Verify `python sim_overhaul.py --assert-mode` passes before opening a PR.

Feel free to open an Issue for bug reports, 1836–1936 observer balance feedback, or feature ideas!
