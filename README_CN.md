[English](README.md) | [简体中文](README_CN.md)

# 铁与蒸汽：海军大修 Iron & Steam: Naval Overhaul `[早期测试版 v0.2.1]`

[![Steam Workshop](https://img.shields.io/badge/Steam%20Workshop-3726415174-1b2838?logo=steam)](https://steamcommunity.com/sharedfiles/filedetails/?id=3726415174&l=schinese)
[![Victoria 3](https://img.shields.io/badge/Victoria%203-1.15.*-blue)](https://store.steampowered.com/app/529340)
[![Multiplayer](https://img.shields.io/badge/Multiplayer-Synchronized-brightgreen)](#版本信息)

> **⚠ 早期测试版说明（v0.2.1 Demo）：**本 Mod 目前仍处于**早期可玩 Demo** 开发阶段。核心海战机制、10 槽舰船设计器以及离线数值回归校验均已可正常运行，但长线 AI 造舰配比、大后期节奏与更多风味事件仍在持续打磨中。非常欢迎反馈 Bug、提出平衡建议，或直接加入协作开发！

**《铁与蒸汽：海军大修》**是面向 **Victoria 3 (`1.15.*`)** 的海军系统大修 Mod，全面重构海上探测、接敌规模、舰船改装、破交封锁与制海权博弈，让海权争夺、商路袭扰与主力决战真正具备战略与经济分量。

**加载顺序：**建议放在基础框架类 Mod（如 Community Mod Framework）之后、大型全面修改 Mod 之前。与 **[Naval Treaty Expanded（海军条约拓展）](https://steamcommunity.com/sharedfiles/filedetails/?id=3838936983)** 在任意加载顺序下完全兼容。

---

## 开源协作 —— 欢迎通过 GitHub 加入开发！

本项目已在 GitHub 完全开源，**诚邀各位玩家与 Modder 一起参与共建**！无论是数值平衡调整、1836–1936 观察者模式长线测试、风味事件与日志扩充、UI 优化、AI 行为调优，还是与其他 Mod 的兼容补丁，都非常欢迎你的加入：

- **GitHub 仓库**：<https://github.com/NoFires/victoria3-naval-overhaul>
- 仓库内自带离线仿真与回归校验脚本（`python sim_overhaul.py --assert-mode`），方便协作者在提 PR 前一键验证结构、科技前置与海战克制数值。
- 欢迎随时提交 Issue、平衡性讨论或 Pull Request！

---

## 兼容性说明

本 Mod 对海军法案、海军任务、AI 策略与海战接敌规模公式采用增量注入（`INJECT:` / `TRY_INJECT:`）与定向替换（`REPLACE:`），最大限度减少与其他 Mod 的冲突。

- **[Naval Treaty Expanded（海军条约拓展）](https://steamcommunity.com/sharedfiles/filedetails/?id=3838936983)** —— 官方搭档 Mod，完全兼容并专门围绕吨位条约做了联动设计（见下文）。
- 由于需要扩展十槽界面与底层舰船参数，本 Mod 修改了基础舰种定义、改装槽位、老兵等级以及舰船设计器弹窗（`gui/ship_designer_popup.gui`），因此会与同样重做舰船设计器 UI 或整包替换所有原版舰种的 Mod 产生冲突。

---

## 当前版本内容（`v0.2.1 Demo`）

### 海上探测与海战接敌规模重做
- 基于舰队**探测（Detection）**与**可见度（Visibility）**的比值动态缩放**海战接敌规模**（限制在 `0.35x` 至 `2.5x` 之间），防止庞大的主力舰队被极少数零星分散舰船无限拖住。
- 重调各类海军任务的索敌与隐蔽修正：护航、巡逻与拦截奖励侦察能力，而破交袭扰则更奖励隐蔽与突袭效率。
- 重做舰船老兵成长体系，让身经百战的舰队在持续作战韧性、整备恢复与侦察索敌上获得实质回报。

### 10 槽舰船设计器与四极克制闭环
- 将舰船设计器扩展为 **6 个核心槽位**（船体结构、装甲、主炮、副炮武装、动力推进、续航里程）+ **4 个功能性战术槽位**（火控侦察、损管生存、特种武装/防空反潜、续航支援），并同步扩展了船坞设计器 UI。
- 新增多种船体与副炮模块，并加入 13 种特色战术配件：火控雷达、侦察水上飞机、声呐套件、高炮指挥仪、损管中心、鱼雷发射管、自动装弹机、眩晕迷彩、潜艇通气管、水听器阵列、装甲弹药库、附加燃料舱与扫雷具。
- 高等级配件均伴随可见度上升、补给消耗或战略商品（无线电、石油、橡胶）代价，杜绝无脑全拉满。
- 构建清晰的四极克制闭环（**主力舰 ↔ 潜艇 / 鱼雷艇 ↔ 屏卫驱逐舰 ↔ 速射轻巡洋舰**），同时为全部 22 个舰种配置了通过科技树校验的开箱即用**默认蓝图**，大幅减轻大后期与联机微操负担。

### 战略海战与 AI 适配
- 强化海军封锁、沿海炮击与破交袭扰的战略和经济杀伤力，并将持续行动能力与海上存在度及补给网完整度紧密挂钩。
- 同步调整海军法案（商业海军、绿水学派、专业海军、炮舰外交）以及海军军备竞赛日志与相关事件。
- 调整 AI 舰船设计复杂度上限，并引入基于军费档位、财政债务、战时意图与市场供需的配件权重及随机性，确保 AI 能够造出战力合格、配置多元且财政可持续的舰队。

### 与《海军条约拓展》的战略联动
- 专为搭配 **[Naval Treaty Expanded（海军条约拓展）](https://steamcommunity.com/sharedfiles/filedetails/?id=3838936983)** 使用而设计。
- 条约对主力舰与巡洋舰的吨位限制，让每一次 10 槽现代化改装都成为“质与量”之间的真实博弈。
- 不受主力舰吨位封顶限制的护航驱逐舰与潜艇（搭配通气管、水听器与绿水学派学说），将成为受限海军强国与中小海权国家手中极具威胁的不对称王牌。

---

## 版本信息

- **当前版本**：`v0.2.1`（早期测试版 Demo）
- **支持语言**：简体中文、English（完整双语本地化）
- **联机支持**：完全支持多人联机同步
- **支持游戏版本**：Victoria 3 **`1.15.*`**
- **Steam 创意工坊**：<https://steamcommunity.com/sharedfiles/filedetails/?id=3726415174>
- **GitHub 开源地址**：<https://github.com/NoFires/victoria3-naval-overhaul>
