# Pro Cycling Plan & Workouts Skill (`pro_cycling_plan`)

**English** | **中文说明见下方**

This repository contains three separate components: `SKILL.md` (agent instructions), `src/tier_calculator.py` (workout generator), and `mcp/intervals_mcp_server.py` (Intervals.icu account tools). Installing the skill does not configure MCP. The classification tables below describe training rules; section 5 documents current implementation limits.

本仓库包含排课规则、Python 计算器与 Intervals.icu MCP 三部分。安装 Skill 后还需单独连接 MCP，才能读取账号和写入日历。下方分档表是训练规则说明，当前代码限制见第 5 节。

**目标优先规划**：先确定比赛/目标日期、提升周期、主次目标与实际可用时间，再安排基础、构建、专项、恢复和减量。支持 FTP、爬坡、起伏路拉扯、短冲刺、4 小时耐受与热适应；采用 A/B/C 优先级、复测和疲劳反馈调整。规则摘要与证据边界见 [周期化参考](references/goal-periodization.md)，完整示例见 [第 6 节](#6-goal-based-example--目标规划示例)。这是 Skill 的规划能力，尚未新增 Python CLI/MCP 的目标参数。

**持续自适应更新**：首次询问周TSS范围/上限、极化（PI>2）或金字塔偏好；>10h周更主动建议极化，并给部分Z2课明确缓坡任务。输出每课估算TSS、kJ和粗略kcal，骑后根据RPE、补给与主要限制感调整后续。12张图已转录为 [11种独立课表](references/image-workouts.md)，原图时长歧义/负荷标注单独保留。[查看初始询问、12h周计划、Z2爬坡与反馈改课的完整预览](examples/adaptive-preview.md)。

An open-source AI Agent Skill, Polarized Training Planner & [Intervals.icu](https://www.intervals.icu/) MCP Toolkit that adapts real **WorldTour Pro cycling workouts** into personalized, physiologically calibrated training sessions based on **6 core dimensions**:
1. **Power-to-Weight Ratio (`W/kg`)** from **Weight (kg)** + **CP60 or CP20** (`Full Pro` / `Scaled 退阶` / `Double-Scaled 退退阶`)
2. **Optional `CP1` (1-Minute Max Power)** for Anaerobic Phenotype Calibration (`Puncheur/Sprinter` vs. `Diesel/Time-Trialist`)
3. **Weekly Cycling Time Commitment** (`0-5h` / `5-10h` / `10h+` per week)
4. **Leg Strength Training Interference** (`None` vs. `Leg Strength Training -> automatic 20%-40% interval volume reduction`)
5. **Rider Age Range** (`<30`, `30-44`, `45-54`, `55+` recovery & microcycle adjustments)
6. **Indoor vs. Outdoor Environment** (`Indoor smart trainer -> 25%-40% shorter duration + 3%-5% thermal power adjustment`)

## 1.  Classification  / 骑手分类

### A. Base W/kg Tier (`CP60` or `CP20 * 0.95`) / 功体比三级分档

| Tier / 档位 | Male FTP W/kg | Female FTP W/kg | Male CP20 W/kg | Base Scaling Rule / 基准缩放规则 |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Full Pro (与 Pro 一致)** | `>= 4.5 W/kg` | `>= 3.9 W/kg` | `>= 4.75 W/kg` | **100% Pro Volume & Intensity**: 2.5–4.5h outdoor duration, full interval sets (`6x20m LT1`, `10x9m LT2`), 80–120g/h carb fueling. |
| **Tier 2: Scaled (退阶档)** | `3.2 - 4.4 W/kg` | `2.8 - 3.8 W/kg` | `3.35 - 4.65 W/kg` | **-30% to -40% Interval Volume**: Core stimulus preserved, recovery +30–60s, target intensity -0% to -3% FTP. |
| **Tier 3: Double-Scaled (退退阶档)** | `< 3.2 W/kg` | `< 2.8 W/kg` | `< 3.35 W/kg` | **-50% to -60% Interval Volume**: Compact sets (`3x12m LT1`, `4x7m LT2`), recovery +1–2m, supra-threshold target -5% to -8% FTP. |

* **Optional `CP1` (1-Minute Power) Calibration (`CP1 / FTP` Ratio)**:
  * **Puncheur / Sprinter (`CP1 / FTP > 2.2`)**: Uses `FTP = CP20 * 0.92`; keeps full 140%–155% FTP short spikes, extends recovery +30–60s, caps steady LT1/LT2.
  * **Balanced All-Rounder (`1.85 <= CP1 / FTP <= 2.2`)**: Uses standard `FTP = CP20 * 0.95`.
  * **Diesel / Time-Trialist (`CP1 / FTP < 1.85`)**: Uses `FTP = CP20 * 0.96`; caps 10s–30s fast-starts and spikes at `125%–135% FTP` to prevent premature failure.

### B.  Real-World Modifiers /实际修正

| Dimension / 维度 | Category / 分档 | Scaling Adjustment / 课表动态修正规则 |
| :--- | :--- | :--- |
| **1. Weekly Cycling Hours (每周骑行时间)** | **`0 - 5h / week`**<br>**`5 - 10h / week`**<br>**`10h+ / week`** | **Low Volume (`0-5h`)**: 2–3 rides/wk; single session capped at **45–75m** (`0.75x` endurance blocks), prioritizes high-density intervals.<br>**Medium (`5-10h`)**: 4–5 rides/wk (80/20 Polarized); weekday 60–90m, weekend 2–3h (`1.0x`).<br>**High (`10h+`)**: 5–6 rides/wk; unlocks full Pro 45–90m Z2 preload & cooldown extensions (`1.2x`). |
| **2. Leg Strength Training (腿部力量训练)** | **No (`无`)**<br>**Moderate (`1x/wk` or >48h)**<br>**Heavy (`>=2x/wk` or <48h)** | **No Strength**: `0%` reduction.<br>**Moderate Leg Strength**: **Reduce interval volume by `-20%`** (e.g., `5x8m -> 4x8m`).<br>**Heavy Squat/Deadlift**: **Reduce interval volume by `-30% to -40%`** (e.g., `6x8m -> 4x7m`), remove >135% FTP high-torque spikes within 36h, enforce 90–95 rpm smooth cadence. |
| **3. Age Range (年龄范围)** | **`< 30` (U30)**<br>**`30 - 44` (Masters A)**<br>**`45 - 54` (Masters B)**<br>**`55+` (Senior Masters)** | **`< 30`**: Standard recovery & 2–3 hard days/wk.<br>**`30 - 44`**: Inter-rep recovery **+15–30s**, min 48h between hard sessions.<br>**`45 - 54`**: Interval volume **-10% to -15%**, recovery **+30–60s**, warmup >=15m, max 2 hard days/wk (or 9-day microcycle).<br>**`55+`**: Interval volume **-20% to -30%**, peak VO2/spike target **-3% to -5% FTP**, recovery **+60–90s**. |
| **4. Indoor vs. Outdoor (室内与室外区别)** | **Outdoor (室外公路)**<br>**Indoor (室内骑行台)** | **Outdoor**: 100% duration (2–4.5h) and 100% target `%FTP`.<br>**Indoor Trainer**: Zero coasting + high thermal load -> **Shorten total duration by `25%–40%`** (cap at **45–90m**, warmup 10–15m, cooldown 5–10m) and lower LT2/VO2Max wattage by **`3%–5% FTP`**. |

## 2. How to Use  / 接入指南

Keep the complete repository in the skill folder so the agent can also access `src/` and `mcp/`. Installing the skill adds instructions; installing the MCP SDK and connecting your account are separate steps. Commands below use Windows PowerShell. If the target already exists, update that checkout instead of cloning over it.

保留完整仓库目录，不要只复制 `SKILL.md`。以下命令用于安装 Skill；连接 Intervals.icu 还需完成第 3 节。

### A. Codex desktop / CLI / IDE extension

```powershell
git clone https://github.com/veibae37/pro_cycling_plan.git "$env:USERPROFILE/.agents/skills/pro-cycling-workouts"
```

Open a new session and invoke `$pro-cycling-workouts`, or ask the agent to use this skill. Project-only installation can use `.agents/skills/pro-cycling-workouts/` under the project root. See [official OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills).

### B. Claude Code

```powershell
git clone https://github.com/veibae37/pro_cycling_plan.git "$env:USERPROFILE/.claude/skills/pro-cycling-workouts"
```

Invoke `/pro-cycling-workouts` or ask in natural language. Project-only installation can use `.claude/skills/pro-cycling-workouts/`. See [Claude Code skills](https://code.claude.com/docs/en/skills).

### C. Cursor and Windsurf / Cascade

- **Cursor:** use `.cursor/skills/pro-cycling-workouts/` in your project, or the user-level `.agents/skills/` location shown for Codex. Use the native skill folder rather than renaming the file to `.mdc`. See [Cursor skills](https://cursor.com/docs/skills).
- **Windsurf / Cascade:** use `.windsurf/skills/pro-cycling-workouts/`. Newer Devin Desktop versions prefer `.devin/skills/` and still read the legacy location. Check the directory supported by your installed version. See [Cascade skills](https://docs.devin.ai/desktop/cascade/skills).

### D. Gemini CLI

```powershell
gemini skills install https://github.com/veibae37/pro_cycling_plan.git
gemini skills list --all
```

After installation, ask Gemini to use `pro-cycling-workouts`. See [Gemini CLI skills](https://geminicli.com/docs/cli/skills/). MCP is configured separately through Gemini's `mcpServers` settings; see [Gemini MCP documentation](https://geminicli.com/docs/tools/mcp-server/).

### E. Claude Projects and ChatGPT Projects / Custom GPTs

1. Upload `SKILL.md`, the Markdown files in `references/`, `scripts/plan_metrics.py`, and `src/tier_calculator.py` to project files or GPT Knowledge. Keep references available with the skill; execution-capable clients can use the metrics script to estimate custom workouts.
2. Copy the appropriate adapter into project instructions or GPT Instructions: [Claude adapter](adapters/claude-project-instructions.md) or [ChatGPT adapter](adapters/chatgpt-custom-gpt-prompt.md).
3. Enable code execution where available and explicitly ask the agent to run the calculator. If execution is unavailable, run it locally using section 4 and provide the JSON result.
4. Uploading these files does not connect Intervals.icu. Claude Desktop can use the local configuration below. ChatGPT web needs a supported remote MCP/plugin connection or Secure MCP Tunnel; it does not read local Codex configuration files. This repository currently provides a stdio server, without a remote deployment or tunnel setup. See [OpenAI connection requirements](https://developers.openai.com/plugins/deploy/connect-chatgpt).

对于网页项目，上传文件后即可提供规则上下文；是否能执行计算器取决于客户端能力。账号读写必须另外接入 MCP，不能把上传文件当作连接成功。

## 3. How to Set Up Intervals.icu MCP (`mcp/intervals_mcp_server.py`) / 如何配置 Intervals.icu MCP 自动读写日历

The server runs as a local **stdio** process launched by your agent. You do not need a separate terminal running the server. A successful local connection still needs valid Intervals.icu credentials before account tools can work.

MCP 由 Agent 在本机启动，通过标准输入输出通信。先完成依赖安装，再配置客户端；工具显示已连接后，先测试读取账号。

### Step 1: Get Your Intervals.icu Athlete ID & API Key (获取密钥)

1. Log into [Intervals.icu Settings](https://intervals.icu/settings), find **Developer Settings**, and generate an API key.
2. Confirm your Athlete ID, for example `i123456`.
3. Keep credentials in private local settings. Do not put a real key in this README, chat prompts, or tracked repository files. See [Intervals.icu API access](https://forum.intervals.icu/t/api-access-to-intervals-icu/609).

### Step 2: Install Dependencies (安装轻量依赖)

From the repository root / 在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install mcp
```

The server uses Python's standard library for HTTP requests, so `httpx` is not a direct dependency. Keep `.venv/` out of Git commits. Install dependencies in the same Python environment used by the MCP client's `command`.

### Step 3A: Claude Desktop / Claude Code / Cursor / Cascade (JSON)

Replace `C:/path/to/pro_cycling_plan` with the absolute path to your checkout, and replace both credential placeholders. Windows JSON paths can use forward slashes. On macOS/Linux use the virtual environment's `.venv/bin/python` instead.

把下面两处路径改为实际仓库路径，并填写账号与密钥。将条目合并到已有的 `mcpServers` 中，保留其他服务器配置。

```json
{
  "mcpServers": {
    "intervals-icu": {
      "command": "C:/path/to/pro_cycling_plan/.venv/Scripts/python.exe",
      "args": ["C:/path/to/pro_cycling_plan/mcp/intervals_mcp_server.py"],
      "env": {
        "INTERVALS_ATHLETE_ID": "i123456",
        "INTERVALS_API_KEY": "REPLACE_WITH_YOUR_API_KEY"
      }
    }
  }
}
```

- **Claude Desktop (Windows):** Settings → Developer → Edit Config opens `%APPDATA%\Claude\claude_desktop_config.json`. Save, fully quit, and restart. See [local MCP setup](https://modelcontextprotocol.io/docs/2026-07-28/develop/connect-local-servers).
- **Claude Code:** project configuration is `.mcp.json`; user-scoped entries are stored in `~/.claude.json`. For a project file, accept the connection prompt and use `/mcp` to inspect status. Keep secret-bearing project configuration out of Git. See [Claude Code MCP](https://code.claude.com/docs/en/mcp).
- **Cursor:** use user-level `~/.cursor/mcp.json`, or project-level `.cursor/mcp.json` with credentials excluded from Git. See [Cursor MCP](https://cursor.com/docs/mcp).
- **Windsurf / Cascade:** open the MCP configuration from the client's settings and merge the entry under `mcpServers`; the path varies by version. See [Cascade MCP configuration](https://docs.devin.ai/desktop/cascade/mcp).

### Step 3B: Codex desktop / CLI / IDE extension (TOML)

Merge this into your private user-level `~/.codex/config.toml`. Do not replace the whole file. Replace the paths and credentials as above.

```toml
[mcp_servers.intervals-icu]
command = "C:/path/to/pro_cycling_plan/.venv/Scripts/python.exe"
args = ["C:/path/to/pro_cycling_plan/mcp/intervals_mcp_server.py"]

[mcp_servers.intervals-icu.env]
INTERVALS_ATHLETE_ID = "i123456"
INTERVALS_API_KEY = "REPLACE_WITH_YOUR_API_KEY"
```

Restart the client and inspect `/mcp`, or run `codex mcp list`. Local Codex clients on the same host share this configuration. See [official OpenAI MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

### Step 4: Available MCP Tools

- `get_athlete_profile()`: returns `id`, `name`, `weight_kg`, and `sportSettings`. FTP-related values depend on the fields returned inside sport settings; eFTP and W' are not explicitly extracted by this wrapper.
- `get_recent_wellness_and_activities(oldest_date, newest_date)`: returns activities and wellness for the supplied `YYYY-MM-DD` range. Available load metrics and activities depend on API responses and data-source restrictions. This does not itself diagnose fatigue or glycogen depletion.
- `create_intervals_workout(target_date, name, description_code, moving_time_sec)`: writes the supplied workout to the requested calendar date. Supply the actual duration in seconds; omitting it uses the current default of 4,500 seconds.
- `generate_and_push_pro_workout(...)`: generates and immediately writes a workout using rider parameters. It does not preview or automatically incorporate recently fetched wellness data. If passing FTP/CP60, set `is_cp20=false`; the default `true` treats the supplied power as CP20.

`get_fitness_and_recent_rides` is not a tool in this implementation. The correct name is `get_recent_wellness_and_activities`.

### Step 5: Read → preview → write → verify (推荐操作流程)

1. **Read / 读取：** “调用 `get_athlete_profile` 确认账号，再调用 `get_recent_wellness_and_activities` 读取 2026-10-11 至 2026-10-18 的数据；只说明实际返回的指标。”
2. **Preview / 预览：** “使用我的骑士参数运行本地计算器，生成 2026-10-19 的课表，先展示完整步骤、时长和预估负荷。” There is no preview-only MCP tool; use the local calculator or let the agent draft the workout.
3. **Write / 写入：** “把刚才预览的课表通过 `create_intervals_workout` 写入 2026-10-19，传入完整课表文本和总秒数，返回创建结果。”
4. **Verify / 核对：** Open the date in Intervals.icu and inspect the parsed steps, duration, power targets, and any device-sync result.

Both write tools create events with `POST /events`. They do not check duplicates, update existing events, or retry safely after an ambiguous network failure. Check the calendar before repeating a write. Writing to the calendar does not prove that Garmin, Wahoo, or Zwift received a structured workout; parsing and device integrations must be verified separately.

### Troubleshooting / 常见问题

- `No module named mcp.server` or missing `FastMCP`: install `mcp` with the exact interpreter from `command`. Merely finding the repository's `mcp/` directory does not mean the SDK is installed.
- Server does not start: check absolute paths, interpreter availability, JSON/TOML syntax, and the client's MCP logs, then restart the client.
- `Missing INTERVALS_API_KEY`: confirm the key is passed in the server's `env` settings and restart the server.
- HTTP 401/403: check credentials and account permissions. Missing source activities may also reflect API data-source restrictions.
- No account integration was tested just by installing the skill or running the calculator. Verify a read request before attempting a calendar write.

## 4. 中文指南 (Chinese Quick Start)

### 提问模板示例

> **"体重 68kg，CP20 是 265W，CP1 是 540W，年龄 32 岁。我每周骑车大概 6 小时（5-10h 档），每周有 2 次深蹲腿部力量训练（昨天刚练完腿），今天在室内骑行台想练 LT2 阈值课表，请帮我定档、减量并生成 Intervals.icu 代码。"**

不连接 MCP 也能在仓库根目录运行计算器；`-X utf8` 避免 Windows 输出中文时的编码问题：

```powershell
python -X utf8 src/tier_calculator.py --weight 68 --cp20 265 --cp1 540 --hours 5-10 --strength heavy --age 30-44 --model lt2
```

当前代码输出有效 FTP `251.8W`、`3.70 W/kg`、Scaled 档；主训练为 `4x7m @ 87-92% FTP`，恢复 `2m @ 50%`。报告时长为 `66` 分钟，预估 TSS `72`、做功 `808kJ`、补给 `65g/h`。这些是当前计算器输出，不代表精确生理测量；时长偏差见第 5 节。

参数说明：`--cp60` 可用于输入 FTP/CP60；默认室内，`--outdoor` 切换室外；`--weekly` 额外输出周计划摘要。`--model` 可选 `lt1`、`fast_vo2`、`lt2`、`z3_z4_spikes`、`vo2_over_under`、`short_30_30`、`recovery`。周计划输出不会自动写入日历。

## 5. Where to Edit and Current Limits / 修改位置与当前限制

### Where to edit / 按需求找到修改文件

- [SKILL.md](SKILL.md): agent-facing training rules, model descriptions, and output requirements / 排课规则、课表库与输出要求。
- [references/goal-periodization.md](references/goal-periodization.md): goals, periodization, specialty sessions, recovery, assessments, and heat adaptation / 修改目标映射、周期与复测规则。
- [references/image-workouts.md](references/image-workouts.md), [load-and-distribution.md](references/load-and-distribution.md), [feedback-loop.md](references/feedback-loop.md): image transcription, weekly TSS/PI and ongoing feedback / 修改图片课库、周负荷/极化偏好和反馈调整。
- [scripts/plan_metrics.py](scripts/plan_metrics.py): standalone planned-load estimator / 修改逐段NP/TSS、做功/热量及三强度区PI计算；[examples/](examples/)包含可复算输入。
- [src/tier_calculator.py](src/tier_calculator.py): `RiderProfile.analyze()` implements tiers and modifiers; `generate_workout()` generates steps and estimates; `generate_weekly_microcycle()` builds the weekly summary / 修改分档算法、具体课表、时长与负荷计算。
- [mcp/intervals_mcp_server.py](mcp/intervals_mcp_server.py): MCP tools, Intervals.icu request payloads, and calendar writes / 修改账号读取、工具参数与日历写入。
- [adapters/](adapters/): instructions for ChatGPT and Claude projects / 修改网页项目的适配提示词。
- Your private MCP client settings: interpreter/script paths, Athlete ID, and API key / 本机路径与密钥在客户端配置中修改，不能写进公开仓库。

### Current limits / 使用前了解的实现限制

- Training tables, skill prose, adapter prompts, and calculator output are not fully aligned. Ask the agent to identify which source it used. Updating a rule in `SKILL.md` does not change the Python algorithm.
- TSS and kJ use a fixed per-model intensity estimate, not a full integration of workout steps or measured normalized power. Some duration formulas also differ from the emitted steps: LT1 omits extra recovery seconds in its duration calculation, and LT2 approximates its primer duration. Check the actual parsed workout in Intervals.icu.
- Reading wellness does not automatically adjust the generated session. The weekly generator uses fixed schedules rather than enforcing all recovery and weekly-hour rules described above.
- The Python `RiderProfile` supports `sex`, but the CLI and MCP generation tool currently do not expose that parameter and use its default `male`.
- Goal/date-based periodization, Miracle-style sprints, Surges & Settle variants, and heat adaptation are agent-authored planning rules. The CLI/MCP generator still exposes its original fixed models; it does not automatically consume these rules or accept goal, race-date, or plan-length parameters. Custom workout text can be sent with `create_intervals_workout` after review and authorization.
- `scripts/plan_metrics.py` estimates supported constant/range %FTP text and per-session week totals; it does not replace the original calculator, parse activity files or guarantee actual TSS/energy. Three-zone PI requires stated physiological boundaries or explicitly disclosed proxy assumptions; it is not a calculation on the FTP seven-zone labels.
- This server exposes local stdio only. It has no bundled remote deployment, multi-user OAuth flow, event lookup, duplicate prevention, or device-sync verification.

Documentation links checked on 2026-10-18. Client menus and supported locations can vary by installed version. These instructions do not imply a successful live Intervals.icu account test.

## 6. Goal-based Example / 目标规划示例

以下为**假设输入与 Skill 预期输出示范**，不是用户真实数据、现有 CLI 自动生成的周期计划或已经完成的训练结果。

### Input / 用户输入

> 从 2026-10-19 开始训练，2027-01-10 参加预计骑行 4 小时的起伏路公路活动，做 12 周计划，时区 Asia/Singapore。主目标是提升长距离后段耐受和拉扯后回稳态的能力；次目标是 FTP 从 250W 向 265W 努力。体重 70kg，32 岁，FTP 为近期同协议测试值，最近每周骑 6 小时，最长 2 小时。每周最多 8.5 小时，周二最多 75 分钟、周三/周四各 60 分钟、周六最多 4 小时、周日通常最多 90 分钟（活动当天可安排 4 小时），周一/周五休息。本周期不安排腿部力量训练；工作日室内、周末室外，已耐受骑中 60g/h 碳水。暂无热适应目标。请给出阶段安排、第 5 周课表和周四的 Intervals.icu 文本。

### Output / 输出节选

**目标卡**：2026-10-19 至 2027-01-10，共 12 周；70kg、FTP 250W、3.57 W/kg，Scaled 模板起点。以 4 小时活动的后段稳定性为主要验收，FTP 265W 为期望目标，不保证达成。起伏路提速是比赛专项的一部分，暂不叠加独立短冲刺或热适应训练块。

**阶段安排**（小时含全部骑行；不是每周必须完成的额度）：

- 第 1–3 周，10/19–11/08：基础与配速，周时长 6 → 6.5 → 7h，长骑从已适应的 2h 渐进至 2.5h。
- 第 4 周，11/09–11/15：恢复/评估，约 4.5h；已有有效基线，无需第 1 周再测。若恢复充分，用同协议测试替代当周一次质量课。
- 第 5–7 周，11/16–12/06：构建，6.5 → 7 → 7.5h，阈值与可控提速分开安排，长骑逐步接近 3h。
- 第 8 周，12/07–12/13：恢复/评估，约 5h；按实际测试调整区间，不能提前把目标 265W 当成当前 FTP。
- 第 9–10 周，12/14–12/27：专项，8 → 8.5h，恢复良好再尝试 3.5–4h 的路线/补给演练；未准备好则缩短，不为凑时长硬骑。
- 第 11–12 周，12/28–01/10：赛前减量，约 5h、3h 赛前训练，保留少量熟悉强度。末周另计约 4h 活动，总骑行约 7h；两周赛前训练相对峰值周重复两次的 17h 约减 53%。

**第 5 周，11/16–11/22：6.5h / 390 分钟**。A/B/C 是对目标的重要程度，不是强度分区。

- 周一：完全休息。
- 周二 A，75min：渐进热身、2×15min @ 90–95% FTP（组间 5min 轻松），其余轻松耐力与冷身；服务持续输出。
- 周三 B，60min：轻松 Z2，约 60–70% FTP，保持能交谈的强度。
- 周四 B，60min：可控 Surges & Settle，2×8min，练提速后回到稳定功率；完整文本如下。
- 周五：完全休息。
- 周六 A，150min：轻松长骑，按当前耐受练骑姿和补给；沿用已耐受的 60g/h，骑中约 150g 碳水，按天气与个人出汗补水。
- 周日 C，45min：极轻松恢复骑；疲劳时直接休息，不加入冲刺。

**周四课表：60min，自定义变式**。每个 8min 主组在第 2、4、6 分钟开始处以 15 秒提速替换稳态时间，不额外增加组时长。

```text
Warmup
- 15m 55%

Surges and Settle 1
- 2m 82%
- 15s 125%
- 1m45s 82%
- 15s 125%
- 1m45s 82%
- 15s 125%
- 1m45s 82%

Recovery
- 4m 50%

Surges and Settle 2
- 2m 82%
- 15s 125%
- 1m45s 82%
- 15s 125%
- 1m45s 82%
- 15s 125%
- 1m45s 82%

Endurance
- 15m 65%

Cooldown
- 10m 50%
```

时长：15 + 8 + 4 + 8 + 15 + 10 = **60min**；按 FTP 250W 与上述目标功率逐段计算，机械做功约 **581.5kJ**。以1秒目标序列和30秒移动平均估计NP约174W、TSS约**49**；假设20–25%机械效率，粗略热量约**556–695kcal**，不等同于精确代谢测量。若授权写日历，使用 `create_intervals_workout`，日期 `2026-11-19`、`moving_time_sec=3600`；本示例未调用日历写入。

**反馈规则**：纯时间冲突先删周日 C、再缩周三 B；明显疲劳时可取消 A，漏课不补堆。每周看完成率、长骑后段功率/RPE、胃肠与次日恢复；评估周用同协议复测 FTP。若长骑后仍明显疲惫，下一周保持或回退时长，不继续加量。目标若改为长坡、短冲刺或热适应，先替换训练重点，再重排恢复预算。

## 7. Adaptive Preview / 负荷、极化与反馈示例

参见 [完整预览](examples/adaptive-preview.md)：假设已适应10–12h的骑手选择周TSS500–600和极化偏好，示例计划为12h、约545TSS、低/中/高648/24/48min，PI约2.26。90min Z2缓坡课包含2×20min坡上低区，约55TSS、806kJ、770–960kcal。这里的阈值、训练量与反馈都是演示，不是所有人的默认处方。

反馈后补问全课/主组RPE、失败时间、燃料、腿部与呼吸/心率限制以及恢复；暂定原因可混合，随后修订24–48h与剩余周，不追补TSS。真实续接记录保存在训练目录 `.training-state/state.json`（Git忽略）；无持久存储能力时输出续接摘要，不承诺跨新聊天记得，也不声称已自动编辑日历。

```powershell
python -X utf8 scripts/plan_metrics.py --week examples/polarized-week.json
python -X utf8 scripts/plan_metrics.py --workout examples/z2-climbing.txt --ftp 250
python -X utf8 scripts/plan_metrics.py --zone-minutes 648 24 48
```
