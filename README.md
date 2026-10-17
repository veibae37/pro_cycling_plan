# Pro Cycling Plan & Workouts Skill (`pro_cycling_plan`)

**English** | **中文说明见下方**

This repository contains three separate components: `SKILL.md` (agent instructions), `src/tier_calculator.py` (workout generator), and `mcp/intervals_mcp_server.py` (Intervals.icu account tools). Installing the skill does not configure MCP. The classification tables below describe training rules; section 5 documents current implementation limits.

本仓库包含排课规则、Python 计算器与 Intervals.icu MCP 三部分。安装 Skill 后还需单独连接 MCP，才能读取账号和写入日历。下方分档表是训练规则说明，当前代码限制见第 5 节。

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

1. Upload `SKILL.md` and `src/tier_calculator.py` to project files or GPT Knowledge.
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

### Step 4: Available MCP Tools (实际提供的四个工具)

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

## 4. 中文快速使用指南 (Chinese Quick Start)

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
- [src/tier_calculator.py](src/tier_calculator.py): `RiderProfile.analyze()` implements tiers and modifiers; `generate_workout()` generates steps and estimates; `generate_weekly_microcycle()` builds the weekly summary / 修改分档算法、具体课表、时长与负荷计算。
- [mcp/intervals_mcp_server.py](mcp/intervals_mcp_server.py): MCP tools, Intervals.icu request payloads, and calendar writes / 修改账号读取、工具参数与日历写入。
- [adapters/](adapters/): instructions for ChatGPT and Claude projects / 修改网页项目的适配提示词。
- Your private MCP client settings: interpreter/script paths, Athlete ID, and API key / 本机路径与密钥在客户端配置中修改，不能写进公开仓库。

### Current limits / 使用前了解的实现限制

- Training tables, skill prose, adapter prompts, and calculator output are not fully aligned. Ask the agent to identify which source it used. Updating a rule in `SKILL.md` does not change the Python algorithm.
- TSS and kJ use a fixed per-model intensity estimate, not a full integration of workout steps or measured normalized power. Some duration formulas also differ from the emitted steps: LT1 omits extra recovery seconds in its duration calculation, and LT2 approximates its primer duration. Check the actual parsed workout in Intervals.icu.
- Reading wellness does not automatically adjust the generated session. The weekly generator uses fixed schedules rather than enforcing all recovery and weekly-hour rules described above.
- The Python `RiderProfile` supports `sex`, but the CLI and MCP generation tool currently do not expose that parameter and use its default `male`.
- `lookup_skills` and `skills:update_skill` mentioned in `SKILL.md` are not provided by this repository. Agents without these tools must edit the local skill file or use their own skill-management mechanism.
- This server exposes local stdio only. It has no bundled remote deployment, multi-user OAuth flow, event lookup, duplicate prevention, or device-sync verification.

Documentation links checked on 2026-10-18. Client menus and supported locations can vary by installed version. These instructions do not imply a successful live Intervals.icu account test.
