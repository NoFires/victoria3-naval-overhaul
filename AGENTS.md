# AGENTS.md — Victoria 3 海战全系统大修 Mod 开发规范

## 1. 环境与目标版本
- **游戏版本**：Victoria 3 **1.15.1 (Ivan-Chai)**
- **原版游戏路径**：`C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\game`
- **Mod 根目录**：当前工作目录
- **联机兼容性**：`.metadata/metadata.json` 必须保持 `multiplayer_synchronized = true`。严禁使用导致联机 OOS 的非确定性状态或本地状态分支。

## 2. 核心设计约束
- **先逆向、再改数**：任何数值调整必须先核实原版 `00_defines.txt`、游戏概念本地化或脚本源码的真实公式，禁止拍脑袋编造机制。
- **最小化 GUI 覆盖**：除必要修改外，不覆盖无关原版 GUI 文件。舰船设计器扩展仅改动 `gui/ship_designer_popup.gui`。
- **10 槽位结构**：
  - 6 个核心槽（`utility = no`）：`ship_mod_slot_hull`, `ship_mod_slot_armor`, `ship_mod_slot_guns`, `ship_mod_slot_secondary`, `ship_mod_slot_propulsion`, `ship_mod_slot_range`
  - 4 个战术 Utility 槽（`utility = yes`）：`ship_mod_slot_utility_1` ~ `ship_mod_slot_utility_4`
- **无脑拉满惩罚 & PVP 减负**：
  - 高级配件必须伴随 `visibility`、`supply_cost`、维护费或 `max_distance_to_port` 代价，确保四极克制闭环（主力舰 ↔ 潜艇/鱼雷 ↔ 屏卫驱逐 ↔ 速射轻巡）；
  - 所有舰种必须配置开箱即用的均衡 `default_modifications` 默认蓝图，照顾 PVP 与单机后期体验。
- **AI 同步匹配**：修改槽位数后，必须同步在 `ai_strategies` 中上调 `max_ship_design_complexity` 并为所有配件编写合理 `ai_weight` 与供需感知权重。

## 3. 目录与沙盒约定
- 根目录下的 `sim_overhaul.py` 为本地离线数值推演、VFS 合并检验与静态审计工具，游戏不加载；`docs/architecture/review/` 用于存放架构评审报告，均未通过 Junction 映射至游戏 Mod 目录。
- 修改 `ship_types` 或 `ship_modifications` 前，先通过 `python -B sim_overhaul.py --assert-mode` 验证 VFS 冲突、UTF-8 BOM、双语本地化闭包、AI 复杂度预算与 6 步战斗模型数值平衡。
- 所有新增 Key 均需同时提供 `localization/simp_chinese/` 与 `localization/english/`，确保 `error.log` 零缺失报错，且 `.txt` / `.yml` / `.gui` 文件均保留 UTF-8 BOM（`EF BB BF`）。
