[English](README.md) | [简体中文](README_CN.md)

# Iron & Steam: Naval Overhaul `[Early Demo v0.1.1]`

[![Steam Workshop](https://img.shields.io/badge/Steam%20Workshop-3726415174-1b2838?logo=steam)](https://steamcommunity.com/sharedfiles/filedetails/?id=3726415174)
[![Victoria 3](https://img.shields.io/badge/Victoria%203-1.15.*-blue)](https://store.steampowered.com/app/529340)
[![Multiplayer](https://img.shields.io/badge/Multiplayer-Synchronized-brightgreen)](#version-info)

> **⚠️ Early Demo Notice (`v0.1.1`):** This mod is currently in an **early playable demo** stage. Core naval combat mechanics, the 10-slot ship designer, and offline numerical regression checks are up and running, while long-campaign AI fleet composition, late-game pacing, and additional flavor events are still being actively tuned. Bug reports, balance feedback, and direct collaboration are very welcome!

**Iron & Steam: Naval Overhaul** is a comprehensive naval warfare overhaul for **Victoria 3 (`1.15.*`)**. It overhauls naval detection, engagement battle size, ship customization, convoy raiding, blockades, and maritime power projection—giving sea control, commerce warfare, and decisive fleet engagements genuine strategic and economic weight.

**Load Order:** Recommended after foundational framework mods (such as Community Mod Framework) and before major total-conversion mods. Fully compatible with **[Naval Treaty Expanded](https://steamcommunity.com/sharedfiles/filedetails/?id=3838936983)** in any load order.

---

## Open-Source Collaboration — Join Us on GitHub!

This project is open source on GitHub, and **players and fellow modders are warmly invited to collaborate**! Whether you want to help with balance tuning, 1836–1936 observer-mode stress tests, flavor events and journal entries, UI polish, AI behavior tuning, or compatibility patches for other mods, your help is welcome:

- **GitHub Repository**: <https://github.com/NoFires/victoria3-naval-overhaul>
- Includes an offline simulator & regression verification script (`sim_overhaul.py --assert-mode`) so contributors can verify structure, tech-tree prerequisites, and naval combat counter matrices in one command before opening a PR.
- Feel free to open an **Issue**, balance discussion, or **Pull Request**!

---

## Compatibility Notes

This mod uses additive injection (`INJECT:` / `TRY_INJECT:`) and targeted replacement (`REPLACE:`) for naval laws, naval missions, AI strategies, and the naval battle size formula to minimize conflicts with other mods.

- **[Naval Treaty Expanded](https://steamcommunity.com/sharedfiles/filedetails/?id=3838936983)** — Official companion mod, fully compatible and specifically integrated around treaty tonnage mechanics (see below).
- Because this mod implements a 10-slot ship designer and expanded ship stat balancing, it modifies base ship type definitions, modification slots, veterancy levels, and the Ship Designer popup UI (`gui/ship_designer_popup.gui`). It will conflict with other mods that rework the Ship Designer UI or wholesale replace all vanilla ship types.

---

## Current Features (`v0.1.1 Demo`)

### Naval Detection & Battle Size Overhaul
- Dynamically scales **Naval Battle Size** based on the ratio of fleet **Detection** to enemy **Visibility** (clamped between `0.35x` and `2.5x`), preventing massive main battle fleets from being endlessly stalled by tiny dispersed detachments.
- Rebalances detection and visibility modifiers across naval missions: escort, patrol, and interception reward reconnaissance, while convoy raiding rewards stealth and strike efficiency.
- Overhauls ship veterancy progression so battle-hardened fleets earn tangible rewards in sustained combat resilience, readiness recovery, and reconnaissance.

### 10-Slot Ship Designer & 4-Pole Counter Loop
- Expands the Ship Designer to **6 core slots** (Hull Structure, Armor, Main Guns, Secondary Armament, Propulsion, Range) + **4 functional tactical slots** (Fire Control & Recon, Survivability & Damage Control, Special Armament / AA / ASW, Endurance & Operations), along with an expanded Shipyard Designer UI.
- Adds multiple hull and secondary modules plus 13 distinctive tactical utility modules: Fire Control Radar, Scouting Seaplane, Sonar Suite, AA Director, Damage Control, Torpedo Tubes, Autoloaders, Dazzle Camo, Submarine Snorkel, Hydrophone Array, Reinforced Magazine, Extra Bunkers, and Minesweeping Gear.
- High-tier modules carry tradeoffs in higher visibility, supply consumption, or strategic goods (`radios`, `oil`, `rubber`), preventing mindless max-stat stacking.
- Establishes a clear **4-pole counter loop** (**Capital Ships ↔ Submarines / Torpedo Craft ↔ Screening Destroyers ↔ Rapid-Fire Light Cruisers**), with tech-validated out-of-the-box **default blueprints** for all 22 ship types to cut down late-game and multiplayer micro.

### Strategic Naval Warfare & AI Adaptation
- Strengthens the strategic and economic impact of naval blockades, coastal bombardment, and convoy raiding, tying sustained operations closely to sea presence and supply network integrity.
- Updates naval laws (`Merchant Navy`, `Jeune École`, `Professional Navy`, `Diplomatic Navy`), naval arms race journal entries, and related events.
- Raises AI ship-design complexity limits and introduces budget-, fiscal-stress-, military-wage-, and market-aware modification weights with wider design variance so AI nations build viable, mixed, economically sustainable fleets.

### Strategic Synergy with Naval Treaty Expanded
- Purpose-built to pair with **[Naval Treaty Expanded](https://steamcommunity.com/sharedfiles/filedetails/?id=3838936983)**.
- Treaty tonnage caps on capital ships and cruisers turn every 10-slot modernization into a real strategic tradeoff between **quality vs. quantity**.
- Treaty-exempt escort destroyers and submarines (paired with snorkels, hydrophones, and Jeune École doctrine) become dangerous asymmetric trump cards for treaty-restricted powers and minor maritime nations.

---

## Version Info

- **Current Version**: `v0.1.1` (Early Demo)
- **Supported Languages**: English, 简体中文 (Full bilingual localization)
- **Multiplayer**: Fully `multiplayer_synchronized = true`
- **Game Version**: Victoria 3 **`1.15.*`**
- **Steam Workshop**: <https://steamcommunity.com/sharedfiles/filedetails/?id=3726415174>
- **GitHub Repository**: <https://github.com/NoFires/victoria3-naval-overhaul>
