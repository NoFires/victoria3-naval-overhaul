# Victoria 3 (1.15.1) 海战全系统大修总策划案

## 一、项目定位与已完成的 1.15.1 兼容性修复
- 目标版本：Victoria 3 **1.15.1 (Ivan-Chai)**，联机严格保持 `multiplayer_synchronized = true`。
- 已完成迁移：废弃 `common/script_values/navy_battle_size.txt`，改写为 `common/script_values/command_values.txt` 中的 `naval_battle_size`（保留原版 `is_fleet = yes` 与 `num_assigned_supply_ships` 分支），保留核心公式 `((Own Detection * Enemy Visibility) / (max(Enemy Detection, 1) * max(Own Visibility, 1))) * Enemy Ships * 0.25`。

---

## 二、底层引擎机制逆向基线（`00_defines.txt` & 本地化核实）

### 1. 6 步海战回合结算闭环（`00_defines.txt:863-867, 1995-2078`）
1. **入场与随机目标权重**：`naval_battle_size` 决定接战数（保底 `50%` 入场），每船入场掷一次 `[0.01, 1.0]` 随机权重，决定整场受集火倾向。
2. **就绪度（Readiness）**：开局 `0`，每回合 `+ship_readiness_gain`（默认 `10`），攒满 `100.0` 行动一次（即隐藏的射速/行动频率乘数）。
3. **屏卫分流（Screening vs Vulnerability）**：满屏卫可将 `90%` 攻击从高易损舰分流到屏卫舰；缺屏卫时易损舰额外承伤最高 `+自身易损性%`。
4. **命中与暴击**：
   - `effective_speed = target_speed - (target_visibility / 15)`
   - `miss_chance = clamp(0.5 + 0.03 * (effective_speed - attacker_accuracy * 5), 0.05, 0.90)`
   - 暴击无视目标 `50%` 护甲（`NAVAL_BATTLE_CRIT_ARMOR_REDUCTION = 0.5`）并乘以暴击倍率（鱼雷/潜艇穿重甲核心）。
5. **固定护甲减伤与双血条**：护甲直接减伤（0 伤率 `>50%` 且命中 `>=50` 次加 `+0.1` 撤退意愿）。船体 HP 归零沉没；存活船员 `<=10%` 当场失能并迫使返港（海上归零直接销毁），且船员不满削弱输出。
6. **撤退意愿与脱战**：受损（`<80%/50%/25%`）+ 战力悬殊（`<50%` 且 `>=5` 天）+ 跳弹；破交遇缺屏卫目标时撤退意愿 `×0.25`；逃跑成功率 `0.5 + 航速`。

### 2. 多节点任务衰退过快的逆向分析与对冲
- **原版痛点**：除 `project_power` 外，任务效率硬性 `1/N` 平摊（C++ 引擎）；`NAVAL_MISSION_SUPPLY_COST_FACTOR_SCALING = 0.1`（每多 1 个海区补给船 `+10%`）；`FLEET_PRESENCE_GAIN_PER_DAY = 0.02`（需 50 天攒满）；`FLEET_SPOT_BASE_CHANCE = 0.00005` 过低；`NAVAL_MISSION_BASE_MAX_SEA_REGIONS = 2`。
- **对冲方案**：补给增长降至 `0.04`、每日存在增至 `0.05`（20 天满）、提高 `FLEET_SPOT_BASE_CHANCE` 与侦查系 `ship_detection`、10 槽位赋予 `ship_max_distance_to_port_add/mult`、基础海区数提至 `3`。

### 3. 封锁、岸轰、袭击补给加强
- **封锁（Blockade）**：商船门槛系数 `10 → 4`；封锁对世界市场/海运/吞吐削弱上限提至 `0.90`；生效存在门槛 `0.5 → 0.25`。
- **岸轰（Port Bombardment）**：`BOMBARDMENT_DEVASTATION_MAX` `25.0 → 50.0`；日增率 `0.20 → 0.50`；日拆沿海建筑概率 `0.02 → 0.06`。
- **袭击补给（Raid Supply）**：`CONVOY_RAIDING_STRENGTH_MULT` `0.3 → 0.65`；`FLEET_RAID_MAX_SUPPLY_LENGTH_DIVISOR` `5 → 3`；`SUPPLY_NETWORK_SHORTAGE_PENALTY_MAX` `0.5 → 0.80`。

---

## 三、五大核心系统与 4 阶段路线图

1. **Phase 1（GUI 10 槽扩展 + `defines` 回调与任务加强）**：
   - 仅修改 `gui/ship_designer_popup.gui` 使 `modification_slot` 自适应高度并将选项容器改造成 3 列自动换行 `dynamicgridbox`；
   - 创建 `common/defines/01_naval_overhaul_defines.txt` 与 `common/ship_modification_slots/00_ship_modification_slots.txt`（6 核心槽 + 4 Utility 槽 = 10 槽）。
2. **Phase 2（沙盒验证 + 舰种与 10 槽配件实装）**：
   - 按 6 步真实公式升级 `v3_naval_sandbox.py` 并运行矩阵测试；
   - 实装 `common/ship_types/`、`common/ship_modifications/`（含均衡 `default_modifications`）及中英本地化。
3. **Phase 3（经济反哺 + 公式安全阀 + 任务/海况/老练度）**：
   - 调整 `building_port` / `building_shipyard` PM 产出经济反哺；
   - 为 `command_values.txt` 增加侦查倍率上下限安全阀；
   - 重做 `naval_mission_types`、`naval_battle_conditions`、`ship_veterancy_levels`。
4. **Phase 4（海权 AI + 风味事件与军备竞赛）**：
   - 实装 `ai_strategies`（海洋霸权/破交/近海防御 + `max_ship_design_complexity` 匹配 10 槽）与配件 `ai_weight`；
   - 实装 `on_actions`、`journal_entries`（海军军备竞赛 & 演习）与 `events`。

---

## 四、当前已识别收口项与质量加固（Phase 4.5）

1. **全舰种 `default_modifications` 补齐（PVP & 后期减负）**：
   - 当前仅 `ship_of_the_line`、`frigate`、`early_troop_ship`、`supply_ship` 配有默认蓝图，其余 18 个舰种（含无畏舰、航母、潜艇、驱逐舰）需全部补齐均衡的开箱即用 `default_modifications`。
2. **AI 10 槽复杂度解锁**：
   - `common/ai_strategies/00_default_strategy.txt` 中 `max_ship_design_complexity` 当前仍为原版基础值 `20`，需上调以匹配 10 槽位改装预算，避免 AI 后期因复杂度不足造不出高阶协防舰队。
3. **科技前置与时代沉浸感校准**：
   - 为 `utility_mod_fire_control_radar`、`utility_mod_sonar_suite`、`utility_mod_aa_director`、`utility_mod_snorkel`、`utility_mod_autoloader` 等末期/超前配件补充合理的 `unlocking_technologies` 时代锁，避免 1836–1890 年代过早出现二战级电子/潜艇设备。
4. **本地化 Key 对齐与 `utility` 槽位审查**：
   - 对齐 `common/ship_modifications/` 与 `localization/` 中残留不一致的 Key（如 `utility_mod_sonar_suite` vs `utility_mod_sonar_asw`、`utility_mod_minesweeping_gear` vs `utility_mod_mine_sweeper`、`ship_mod_hull_subdivided` vs `ship_mod_hull_stealth`），确保 `error.log` 零缺失报错。
   - 核查 `utility_1..4` 槽位重复装备同一配件的叠加边界，必要时对高敏配件加设互斥或槽位限制。

---

## 五、与 `Naval Treaty Expanded` 的软兼容与联动策划（Phase 5）

> **核心兼容原则**：
> 1. **能 `INJECT:` 就 `INJECT:`**：修改原版或他方 Mod 对象（如海军学说法律 `common/laws/`、`ai_strategies` 等）时，优先使用 Victoria 3 原生 `INJECT:` / `TRY_INJECT:` 局部注入语法，严禁整文件覆盖原版法律文件，确保与 BPM 等大型政经 Mod 兼容。
> 2. **独立可玩、互不强依赖**：本 Mod 与 `Naval Treaty Expanded` 各自独立可玩，保持 `multiplayer_synchronized = true`。严禁在本 Mod 中直接硬引用 `Naval Treaty Expanded` 未加载的静态对象而导致单开时 `error.log` 报错；跨 Mod 联动通过各自独立的软兼容判定或独立兼容补丁（Compatch）实现。

---

## 六、实证 `INJECT:` / `REPLACE:` 重构与仿真验收结果（已完成）

- **兼容性重构**：移除 `00_default_strategy.txt`、`command_values.txt`、`00_naval_mission_types.txt` 整文件覆盖，落地 [zz_naval_overhaul_strategy.txt](common/ai_strategies/zz_naval_overhaul_strategy.txt)、[zz_naval_overhaul_script_values.txt](common/script_values/zz_naval_overhaul_script_values.txt)、[zz_naval_overhaul_missions.txt](common/naval_mission_types/zz_naval_overhaul_missions.txt) 与 [zz_naval_overhaul_navy_model.txt](common/laws/zz_naval_overhaul_navy_model.txt)。
- **`.txt` 直读仿真器验收 (`sim_overhaul.py --assert-mode`)**：22 舰种全部补齐 `default_modifications` 与互斥 4 战术槽、中英双语本地化零缺失、早期船补给全正、潜艇基础 HP 回拨至 `850`（无屏卫无畏舰战损比 `0.80`、配声呐驱逐反转至 `184.04`、轻巡压制鱼雷艇 `162.72`）、180 天炮击建筑损毁期望收敛至 `4.5` 次。

1. **海军学说法律（Naval Doctrine Laws）`INJECT:` 增强**：
   - 通过 `INJECT:` 精准扩展原版四大海军学说法律（商船海军 `law_merchant_navy`、绿水学派 `law_jeune_ecole`、专业海军/决战学派 `law_professional_navy`、近海防御等）：
     - 将法律效果与本 Mod 的核心机制挂钩（例如：绿水学派强化破交/鱼雷艇与潜艇隐蔽及暴击；专业海军强化主力舰老练度获取、射速/命中与 10 槽复杂度上限；商船海军强化护航屏卫、反潜侦查与多海区补给效率）。
     - 保持 `ai_weight` 中各配件（`ship_mod_capital_doctrine` / `ship_mod_jeune_ecole_doctrine` / `ship_mod_merchant_navy_doctrine` / `ship_mod_coastal_defence_doctrine`）与法律修正同频共振。
2. **战略闭环：“条约限额” × “强海权惩罚”**
   - `Naval Treaty Expanded` 通过 `nte_ship_values.txt` 限制主力舰/巡洋舰有效吨位（驱逐舰/潜艇计 `0` 吨位），本 Mod 通过 `90%` 封锁惩罚与 `80%` 补给短缺惩罚赋予制海权真实痛感。
   - 联动效果：迫使条约缔约国在有限的主力舰吨位内，利用 **10 槽位精兵化 + 4 级老练度**打造“少而精”的条约战列舰；同时放大非对称破交（潜艇/驱逐舰不占条约配额 + `0.65` 破交倍率）的战略威慑，自然推动条约国在修订投票中博弈“收紧/放宽”限额。
3. **军备竞赛与海军条约的阶段衔接（需兼容处理）**
   - 本 Mod 的 `je_naval_arms_race` 与 `Naval Treaty Expanded` 的 `global_naval_limitation_union` 同属海军军备叙事。
   - 兼容方案：在联动补丁或软兼容检测中，当全球海军条约生效时，暂停/转化 `je_naval_arms_race` 的造船补贴修正（避免“签了限武条约仍吃军备竞赛 buff”）；当条约破裂或超标危机爆发时重新激活军备竞赛，形成“竞赛 → 限武 → 破约重燃”周期。
4. **10 槽改装与吨位核算校准**
   - `nte_ship_values.txt` 仅依据基础船型、`power_projection`（溢价上限 `25`）与 `hit_points`（溢价上限 `20`）核算单舰吨位。
   - 兼容平衡：适度为本 Mod 核心增伤/火控/防沉大件附带合理的 `ship_power_projection_add`，防止“高配 10 槽神船”在条约体系下出现账面吨位零增长的过度超模漏洞；同时保留 `lightweight` 轻量化船体与巡洋舰的“条约重巡/袖珍战列舰”玩法空间。
5. **“暴露度（Visibility）” × “吨位造假（Falsification）”外交交互（联动扩展方向）**
   - 结合本 Mod 的 `ship_detection / ship_visibility` 与条约 Mod 的 `nte_tonnage_falsification_active`（吨位造假 `-12%`）：在联动包中可设计“高侦查舰队在海上接触/拦截造假国舰队时，有概率触发违规超吨曝光事件”，让隐蔽度同时服务于战术接战与外交合规。
6. **AI 协同适配**
   - 两个 Mod 同时启用时，AI 既面临条约吨位红线，又面临 10 槽复杂度预算。确保本 Mod 提升 `max_ship_design_complexity` 且全舰种配齐 `default_modifications` 后，AI 在条约限制下仍能造出合格的精锐主力舰与护航/破交编队，避免后期战力一边倒。
