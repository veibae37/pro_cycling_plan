# Pro Cycling Plan & Workouts Skill (`pro_cycling_plan`)

**English** | **中文说明见下方**

An open-source AI Agent Skill, Polarized Training Planner & [Intervals.icu](https://www.intervals.icu/) MCP Toolkit that adapts real **WorldTour Pro cycling workouts** into personalized, physiologically calibrated training sessions based on **6 core dimensions**:
1. **Power-to-Weight Ratio (`W/kg`)** from **Weight (kg)** + **CP60 or CP20** (`Full Pro` / `Scaled 退阶` / `Double-Scaled 退退阶`)
2. **Optional `CP1` (1-Minute Max Power)** for Anaerobic Phenotype Calibration (`Puncheur/Sprinter` vs. `Diesel/Time-Trialist`)
3. **Weekly Cycling Time Commitment** (`0-5h` / `5-10h` / `10h+` per week)
4. **Leg Strength Training Interference** (`None` vs. `Leg Strength Training -> automatic 20%-40% interval volume reduction`)
5. **Rider Age Range** (`<30`, `30-44`, `45-54`, `55+` recovery & microcycle adjustments)
6. **Indoor vs. Outdoor Environment** (`Indoor smart trainer -> 25%-40% shorter duration + 3%-5% thermal power adjustment`)

## 1. Multi-Dimensional Classification Matrix / 多维分档与修正矩阵

### A. Base W/kg Tier (`CP60` or `CP20 * 0.95`) / 功体比三级基准分档

| Tier / 档位 | Male FTP W/kg | Female FTP W/kg | Male CP20 W/kg | Base Scaling Rule / 基准缩放规则 |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Full Pro (与 Pro 一致)** | `>= 4.5 W/kg` | `>= 3.9 W/kg` | `>= 4.75 W/kg` | **100% Pro Volume & Intensity**: 2.5–4.5h outdoor duration, full interval sets (`6x20m LT1`, `10x9m LT2`), 80–120g/h carb fueling. |
| **Tier 2: Scaled (退阶档)** | `3.2 - 4.4 W/kg` | `2.8 - 3.8 W/kg` | `3.35 - 4.65 W/kg` | **-30% to -40% Interval Volume**: Core stimulus preserved, recovery +30–60s, target intensity -0% to -3% FTP. |
| **Tier 3: Double-Scaled (退退阶档)** | `< 3.2 W/kg` | `< 2.8 W/kg` | `< 3.35 W/kg` | **-50% to -60% Interval Volume**: Compact sets (`3x12m LT1`, `4x7m LT2`), recovery +1–2m, supra-threshold target -5% to -8% FTP. |

* **Optional `CP1` (1-Minute Power) Calibration (`CP1 / FTP` Ratio)**:
  * **Puncheur / Sprinter (`CP1 / FTP > 2.2`)**: Uses `FTP = CP20 * 0.92`; keeps full 140%–155% FTP short spikes, extends recovery +30–60s, caps steady LT1/LT2.
  * **Balanced All-Rounder (`1.85 <= CP1 / FTP <= 2.2`)**: Uses standard `FTP = CP20 * 0.95`.
  * **Diesel / Time-Trialist (`CP1 / FTP < 1.85`)**: Uses `FTP = CP20 * 0.96`; caps 10s–30s fast-starts and spikes at `125%–135% FTP` to prevent premature failure.

### B. Four Real-World Modifiers / 四大实战修正维度

| Dimension / 维度 | Category / 分档 | Scaling Adjustment / 课表动态修正规则 |
| :--- | :--- | :--- |
| **1. Weekly Cycling Hours (每周骑行时间)** | **`0 - 5h / week`**<br>**`5 - 10h / week`**<br>**`10h+ / week`** | **Low Volume (`0-5h`)**: 2–3 rides/wk; single session capped at **45–75m** (`0.75x` endurance blocks), prioritizes high-density intervals.<br>**Medium (`5-10h`)**: 4–5 rides/wk (80/20 Polarized); weekday 60–90m, weekend 2–3h (`1.0x`).<br>**High (`10h+`)**: 5–6 rides/wk; unlocks full Pro 45–90m Z2 preload & cooldown extensions (`1.2x`). |
| **2. Leg Strength Training (腿部力量训练)** | **No (`无`)**<br>**Moderate (`1x/wk` or >48h)**<br>**Heavy (`>=2x/wk` or <48h)** | **No Strength**: `0%` reduction.<br>**Moderate Leg Strength**: **Reduce interval volume by `-20%`** (e.g., `5x8m -> 4x8m`).<br>**Heavy Squat/Deadlift**: **Reduce interval volume by `-30% to -40%`** (e.g., `6x8m -> 4x7m`), remove >135% FTP high-torque spikes within 36h, enforce 90–95 rpm smooth cadence. |
| **3. Age Range (年龄范围)** | **`< 30` (U30)**<br>**`30 - 44` (Masters A)**<br>**`45 - 54` (Masters B)**<br>**`55+` (Senior Masters)** | **`< 30`**: Standard recovery & 2–3 hard days/wk.<br>**`30 - 44`**: Inter-rep recovery **+15–30s**, min 48h between hard sessions.<br>**`45 - 54`**: Interval volume **-10% to -15%**, recovery **+30–60s**, warmup >=15m, max 2 hard days/wk (or 9-day microcycle).<br>**`55+`**: Interval volume **-20% to -30%**, peak VO2/spike target **-3% to -5% FTP**, recovery **+60–90s**. |
| **4. Indoor vs. Outdoor (室内与室外区别)** | **Outdoor (室外公路)**<br>**Indoor (室内骑行台)** | **Outdoor**: 100% duration (2–4.5h) and 100% target `%FTP`.<br>**Indoor Trainer**: Zero coasting + high thermal load -> **Shorten total duration by `25%–40%`** (cap at **45–90m**, warmup 10–15m, cooldown 5–10m) and lower LT2/VO2Max wattage by **`3%–5% FTP`**. |

## 2. How to Use Across All AI Platforms / 各大 AI 平台接入指南

### A. Claude Code / Cursor / Windsurf / OpenAI Codex CLI / Gemini CLI

**One-Command Install via Agent Skills CLI (一行命令安装):**

```bash
npx skills add veibae37/pro_cycling_plan
```

**Manual Install for Claude Code (`~/.claude/skills/`):**

```bash
git clone https://github.com/veibae37/pro_cycling_plan.git ~/.claude/skills/pro-cycling-workouts
```

**Manual Install for Cursor / Windsurf:**
Copy `SKILL.md` into `.cursor/rules/pro-cycling-workouts.mdc` or `.windsurfrules`.

### B. Claude.ai Web & Desktop App (Claude Projects)

1. Open [Claude.ai](https://claude.ai/) -> **Projects** -> **Create Project**.
2. Click **Add Content** -> Connect your GitHub repo `veibae37/pro_cycling_plan` (or upload `SKILL.md` and `src/tier_calculator.py`).
3. Set **Project Instructions** to the prompt in `adapters/claude-project-instructions.md`.

### C. ChatGPT (Custom GPTs / ChatGPT Projects)

1. **Create a Shareable Custom GPT**: Go to [ChatGPT GPT Editor](https://chatgpt.com/gpts/editor) -> Paste `adapters/chatgpt-custom-gpt-prompt.md` into **Instructions** -> Upload `SKILL.md` and `src/tier_calculator.py` to **Knowledge** -> Enable **Code Interpreter**.
2. **ChatGPT Projects**: Create a folder in ChatGPT Projects, upload `SKILL.md` + `src/tier_calculator.py`, and paste the adapter prompt into Project Instructions.

## 3. How to Set Up Intervals.icu MCP (`mcp/intervals_mcp_server.py`) / 如何配置 Intervals.icu MCP 自动读写日历

This repository includes a ready-to-run **Model Context Protocol (MCP) Server** (`mcp/intervals_mcp_server.py`) that connects Claude Desktop, Claude Code, Cursor, or Windsurf directly to your [Intervals.icu](https://www.intervals.icu/) account!

### Step 1: Get Your Intervals.icu Athlete ID & API Key (获取密钥)
1. Log into [Intervals.icu Settings](https://www.intervals.icu/settings).
2. Scroll down to **Developer Settings**:
   * Copy your **Athlete ID** (e.g., `i123456`).
   * Click **Generate API Key** and copy the key.

### Step 2: Install Dependencies (安装轻量依赖)
```bash
pip install mcp httpx
```

### Step 3: Configure Your Agent's MCP Settings (配置客户端 JSON)

Add the following block to your `claude_desktop_config.json` (Claude Desktop), `~/.claude.json` (Claude Code), or `.cursor/mcp.json` (Cursor):

```json
{
  "mcpServers": {
    "intervals-icu": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/TO/pro_cycling_plan/mcp/intervals_mcp_server.py"],
      "env": {
        "INTERVALS_ATHLETE_ID": "i123456",
        "INTERVALS_API_KEY": "your_intervals_api_key_here"
      }
    }
  }
}
```

### Step 4: Available MCP Tools (MCP 支持的自动化能力)
* `get_athlete_profile`: Automatically reads your current FTP, Weight, eFTP, W', and sport settings from Intervals.icu.
* `get_fitness_and_recent_rides`: Fetches your live CTL (Fitness), ATL (Fatigue), TSB (Form), and recent 7-day rides to detect glycogen depletion or high fatigue.
* `create_intervals_workout`: Pushes the generated `Warmup / Main Set / Cooldown` workout code directly onto your Intervals.icu calendar for tomorrow's date—automatically syncing to Garmin, Wahoo, or Zwift!

## 4. 中文快速使用指南 (Chinese Quick Start)

### 提问模板示例

> **"体重 68kg，CP20 是 265W，CP1 是 540W，年龄 32 岁。我每周骑车大概 6 小时（5-10h 档），每周有 2 次深蹲腿部力量训练（昨天刚练完腿），今天在室内骑行台想练 LT2 阈值课表，请帮我定档、减量并生成 Intervals.icu 代码。"**

Agent 会自动执行以下计算：
1. **功体比定档**：`FTP = 265 * 0.95 = 252W` (`3.70 W/kg`) -> 匹配 **Tier 2: 退阶档 (Scaled)**。
2. **CP1 表型校准**：`CP1 / FTP = 2.14` -> 均衡偏冲刺型，激活冲刺设定为 `140% FTP`。
3. **四维动态修正**：
   * 每周 `5-10h`：标准极化微周期配比；
   * **有重度腿部力量训练（<48h）**：间歇组数自动 **减量 33%（从 6×8m 减为 4×8m）**，保护下肢恢复；
   * 年龄 `30-44 岁`：组间恢复从 `2m` 延长至 `2m30s`；
   * **室内骑行台**：总时长从 2.5 小时精简至 **68 分钟**，目标阈值功率微调至 `88-91% FTP`。
