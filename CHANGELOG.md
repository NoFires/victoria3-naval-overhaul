[English](CHANGELOG.md) | [简体中文](CHANGELOG_CN.md)

# Changelog — Iron & Steam: Naval Overhaul

## [v0.2.1] - 2026-11-22

### Fixed
- Ship Designer: module icons in the left panel were partially clipped; modification slot heights now fit the 1/2/3-row module grids again.

## [v0.2.0] - 2026-11-21

### Added
- **Naval arms race journal**: active-race modifiers, a 5-year timeout with cooldown, status lines for leading / trailing / wartime, a map mode with rival stripes, and a diplomatic inquiry button.
- **Events**: sail-to-ironclad transition, submarine raiding and convoy reform, fire-control and radar breakthrough, naval aviation trials, and a flagship victory triumph.
- **Naval battle conditions**: night action, sudden squall, submarine ambush waters, heavy swell, clear horizon.
- **Underway Replenishment Gear** utility module for all hull types.

### Changed
- Ship veterancy now uses `REPLACE:` entries in our own file instead of overriding the vanilla file, for better mod compatibility.
- AI keeps utility slots in peacetime (`SHIP_DESIGN_UTILITY_MOD_MIN_SCORE` 1.65 -> 1.125).
- Offline simulator treats torpedo craft as treaty-exempt, matching Naval Treaty Expanded.

### Fixed
- Battle condition triggers now use `scope:attacker` / `scope:defender`.
- Ship designer hull modifier display null context.

## [v0.1.1] - 2026-11-14

### Fixed
- **AI Naval Construction & Strategy Injection (`common/ai_strategies/zz_naval_overhaul_strategy.txt`)**: Restored Vanilla base `max_ship_design_complexity` (`10 + country_rank - 4`) and all 7 `ai_ship_category_*` weights inside `INJECT:ai_strategy_default` so `INJECT:` no longer drops Vanilla baseline categories or complexity capacity.
- **Ship Designer Popup Null Safety (`gui/ship_designer_popup.gui`)**: Restored `datacontext = "[ShipType.GetModifier]"` on the hull base modifier display so inspecting/opening a hull without an active `ShipTemplate` no longer logs null-datacontext GUI errors.
- **Metadata ID**: Populated `"id" : "iron_and_steam_naval_overhaul"` in `.metadata/metadata.json`.

### Changed & Improved
- **Fiscal, Wage & Doctrine-Aware AI Ship Design (`common/script_values/zz_naval_overhaul_script_values.txt`, `common/defines/01_naval_overhaul_defines.txt`, `common/ship_modifications/`)**:
  - Added `ship_mod_budget_high_mult`, `ship_mod_budget_mid_mult`, and `ship_mod_budget_low_mult` driven by `military_wage_level`, `scaled_debt`, `in_default`, `is_at_war`, `country_rank`, and diplomatic strategy.
  - Widened `SHIP_DESIGN_MODIFICATION_RANDOM_FACTOR` (`0.25 -> 0.65`), calibrated `SHIP_CONSTRUCTION_COST_MODIFICATION_LEVEL_FACTOR` (`1.028 -> 1.042`), and tightened market price rejection (`1.45`) so AI navies build varied, budget-appropriate ship designs instead of uniformly maxing every slot.
  - Calibrated `max_ship_design_complexity` offset (`+6`, min `8`) with law/wage/debt modifiers.
- **Naval Treaty Expanded Synergy**:
  - Added `ship_power_projection_add` scaling on offensive ship modifications so heavy armaments directly affect NTE treaty tonnage.
  - Added treaty-aware freeze/pause handling in `je_naval_arms_race` (`common/journal_entries/01_naval_arms_race_je.txt`) when a country enters the Global Naval Limitation Treaty or Naval Holiday.
- **Offline Simulation & Validation (`sim_overhaul.py`)**: Aligned `--assert-mode` complexity checks with the calibrated `+6` baseline and verified all 22 ship types, 295 modifications, and 10 slots.
- **Documentation**: Synced `README.md` and added `README_CN.md` to match Steam Workshop `v0.1.1`.

## [v0.1.0] - 2026-11-14

### Added
- Initial Early Demo release of **Iron & Steam: Naval Overhaul** for Victoria 3 (`1.15.*`).
- Detection/visibility-scaled `REPLACE:naval_battle_size` (`0.35x`–`2.5x`), 10-slot Ship Designer (6 core + 4 tactical utility slots), 13 new utility modules, 4-pole counter matrix, rebalanced naval laws/missions/veterancy, and `sim_overhaul.py` regression suite.
