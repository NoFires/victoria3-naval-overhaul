[English](CHANGELOG.md) | [简体中文](CHANGELOG_CN.md)

# 更新日志 — 铁与蒸汽：海军大修

## [v0.2.1] - 2026-11-22

### 修复
- 舰船设计器：左侧舰船模块图标被部分遮挡；模块槽位高度已恢复，可完整容纳 1/2/3 行模块网格。

## [v0.2.0] - 2026-11-21

### 新增
- **海军军备竞赛日志**：竞赛期间的修正、带冷却的 5 年时限、领先/落后/战时状态描述、带对手条纹的地图模式，以及外交质询按钮。
- **事件**：风帆向铁甲舰过渡、潜艇破交与护航改革、火控与雷达突破、海军航空试验、旗舰凯旋。
- **海战环境**：夜战、突发飑线、潜艇伏击海域、大涌浪、海天澄澈。
- **航行补给装置**实用模块，适用于全部船体。

### 调整
- 舰船老练度改用自有文件中的 `REPLACE:` 条目，不再覆盖原版文件，兼容性更好。
- AI 平时也会保留实用模块槽位（`SHIP_DESIGN_UTILITY_MOD_MIN_SCORE` 1.65 -> 1.125）。
- 离线模拟器将鱼雷艇视为条约豁免，与海军条约拓展保持一致。

### 修复
- 海战环境触发条件改用 `scope:attacker` / `scope:defender`。
- 舰船设计器船体修正显示的空上下文问题。

## [v0.1.1] - 2026-11-14

### 修复
- **AI 造舰与策略注入修复（`common/ai_strategies/zz_naval_overhaul_strategy.txt`）**：在 `INJECT:ai_strategy_default` 中完整保留原版 `max_ship_design_complexity`（`10 + country_rank - 4`）及全部 7 项 `ai_ship_category_*` 权重，修复局部注入覆盖原版基线导致的设计复杂度不足或舰种权重丢失问题。
- **舰船设计器弹窗空指针修复（`gui/ship_designer_popup.gui`）**：将船体基础修正的 `datacontext` 恢复为 `[ShipType.GetModifier]`，避免未选定 `ShipTemplate` 时产生 GUI 报错。
- **元数据 ID 补全**：在 `.metadata/metadata.json` 中补全 `"id" : "iron_and_steam_naval_overhaul"`。

### 调整与优化
- **军费、负债与战略导向的 AI 舰船改装（`common/script_values/zz_naval_overhaul_script_values.txt`、`common/defines/01_naval_overhaul_defines.txt`、`common/ship_modifications/`）**：
  - 新增 `ship_mod_budget_high_mult`、`ship_mod_budget_mid_mult` 与 `ship_mod_budget_low_mult`，结合军费档位（`military_wage_level`）、国债比例（`scaled_debt`）、破产状态、战时意图、国家等级与外交策略动态缩放改装件权重。
  - 提高 `SHIP_DESIGN_MODIFICATION_RANDOM_FACTOR`（`0.25 -> 0.65`）、调整 `SHIP_CONSTRUCTION_COST_MODIFICATION_LEVEL_FACTOR`（`1.028 -> 1.042`）并收紧市场溢价拒绝阈值（`1.45`），防止 AI 无脑全装最高级配件。
  - 将复杂度基线偏置校准为 `+6`（下限 `8`），并与海军法律、军费和债务挂钩。
- **与《海军条约拓展》联动**：
  - 为进攻型船坞改装件补充 `ship_power_projection_add`，使 10 槽强化直接计入 NTE 真实条约吨位。
  - 为 `je_naval_arms_race`（`common/journal_entries/01_naval_arms_race_je.txt`）接入条约冻结联动，签约全球限武条约或海军假日时自动暂停/约束军备竞赛进度。
- **离线仿真校验（`sim_overhaul.py`）**：同步更新 `--assert-mode` 复杂度断言，22 种舰船、295 项改装件与 10 槽结构校验全通过。
- **文档**：同步 `README.md` 并新增 `README_CN.md`，与 Steam 创意工坊 `v0.1.1` 介绍保持一致。

## [v0.1.0] - 2026-11-14

### 新增
- **《铁与蒸汽：海军大修》**面向 Victoria 3（`1.15.*`）的首个早期测试版 Demo 发布。
- 包含基于探测与可见度的 `REPLACE:naval_battle_size`（`0.35x–2.5x`）、10 槽舰船设计器（6 核心槽 + 4 战术槽）、13 种功能性战术配件、四极克制闭环、海军法案/任务/老兵体系重做及 `sim_overhaul.py` 回归校验工具。
