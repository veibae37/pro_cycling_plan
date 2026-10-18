![Pixel-art cyclists climbing a mountain road](docs/images/pro-cycling-banner.jpg)

[简体中文](README.md) · **English**

# Pro Cycling Plan & Workouts

**Goal-based planning · Scaled pro workouts · Load estimates · Intervals.icu MCP**

Adaptive cycling plans built around your goals, available time and recovery, with reusable Agent Skills, a local calculator and optional Intervals.icu integration.

From FTP and climbing to repeated surges and long-ride durability: define the goal and constraints, build the training cycle, select workouts, then adjust from post-ride feedback.

[Showcase](#showcase) · [Rider classification](#classification) · [Install the skill](#installation) · [Connect Intervals.icu](#intervals-mcp) · [Usage & maintenance](#usage)

> [!NOTE]
> This repository has three independent parts: `SKILL.md` planning instructions, a Python calculator, and an Intervals.icu MCP server. Installing the skill does not connect an account. The agent creates multi-week plans from the instructions; see [implementation limits](#limits) for the fixed calculator's capabilities.

<a id="showcase"></a>

## Showcase / From one prompt to an eight-week training calendar

**Describe the goal → Plan the cycle → Estimate load → Authorize import → Adjust after riding**

### Your input

> Use pro-cycling-workouts: I weigh 70 kg, my FTP is 200 W, and I want to improve climbing and repeated surges. I do no strength training. Plan eight weeks of polarized training starting in November 2026, preferably with PI above 1.5. I can ride up to 10 hours per week, rest on Mondays and Fridays, and ride no longer than three hours per session. Keep weekly TSS between 350 and 450. Generate the workouts and write them to Intervals.icu through MCP.

### The resulting plan

**8 weeks · 40 workouts · 8.5–9.5 hours per week · 355–422 weekly TSS**

- **Rider profile:** FTP **200 W / 2.86 W/kg**, with workouts scaled to training history, available time and recovery.
- **Weekly structure:** climbing intervals on Tuesdays and controlled surges on Thursdays; easy climbing and endurance on Wednesdays and Saturdays, with an optional easy Sunday ride.
- **Progression:** three build weeks followed by reduced high-intensity volume in week 4; further specific work in weeks 5–7, then recovery and a repeat of the original interval protocol in week 8.
- **Verified delivery:** 40 structured workouts were imported and read back. Dates, power targets, expanded work/recovery repetitions and durations matched. Device sync requires separate verification.

<details>
<summary><strong>Expand the eight-week load and intensity distribution</strong></summary>

The plan runs from **2026-11-02 to 2026-12-27**, in Asia/Singapore time. TSS below is the value read back from the platform; PI is a proxy estimate based on target power.

- **W1 · Nov 02–08:** 8h30m, **358 TSS**, PI **2.29**; start with 3×2-minute climbing efforts.
- **W2 · Nov 09–15:** 8h50m, **379 TSS**, PI **2.43**; extend to 3×3 minutes.
- **W3 · Nov 16–22:** 9h15m, **402 TSS**, PI **2.53**; progress to 4×3 minutes.
- **W4 · Nov 23–29:** 8h30m, **355 TSS**, PI **2.09**; reduce high-intensity volume and assess recovery.
- **W5 · Nov 30–Dec 06:** 9h15m, **402 TSS**, PI **2.53**; return to 4×3 minutes after recovery.
- **W6 · Dec 07–13:** 9h30m, **420 TSS**, PI **2.64**; extend to 4×4 minutes.
- **W7 · Dec 14–20:** 9h30m, **422 TSS**, PI **2.66**; increase controlled surge repetitions.
- **W8 · Dec 21–27:** 8h30m, **357 TSS**, PI **2.23**; reduce intensity volume and repeat the first week's main set to compare completion quality.

The three intensity zones use **70% / 100% FTP (140 / 200 W)** as proxy boundaries. Low-intensity time dominates, and high-intensity time exceeds moderate-intensity time. These boundaries are not measured LT1/LT2, and the usual seven FTP power zones cannot be substituted directly for three physiological zones. Time above a power boundary during short intervals does not equal time at high oxygen uptake or heart rate.

Recovery weeks retain substantial easy volume to accommodate the requested 350 TSS floor. This case is not a prescription for every rider. Reduce training when clearly fatigued, even below the target; missed TSS is not a debt.

</details>

<details>
<summary><strong>Expand a workout: 60-minute climbing intervals · about 51 TSS · 460 kJ</strong></summary>

The first Tuesday's main set is **3×2 minutes at 220 W**, with two four-minute recoveries at 100 W. Use a safe, continuous climb or a trainer; low-cadence grinding is not required.

```text
Warmup
- 5m 50%
- 5m 60%
- 3m 65%
- 2m 80%

Climb repeats 2x
- 2m 110%
- 4m 50%

Last climb
- 2m 110%

Easy endurance
- 21m 65%

Cooldown
- 10m 50%
```

Duration: `15 + 6 + 8 + 21 + 10 = 60 min`. At FTP 200 W, estimated NP is **142.5 W**, TSS **50.77**, and mechanical work **459.6 kJ**. Assuming 20–25% gross mechanical efficiency, estimated ride energy expenditure is **439–549 kcal**.

Use an already tolerated carbohydrate intake, such as 40–50 g/h, adjusting for gastrointestinal comfort. Match fluid intake to conditions and individual sweat losses. Shorten the workout or rest if the warm-up feels unusually hard.

[Download workout text](examples/climbing-surges-60m.txt) · [Calculation methods](references/load-and-distribution.md)

```powershell
python -X utf8 scripts/plan_metrics.py --workout examples/climbing-surges-60m.txt --ftp 200
```

Keep a blank line after each repeat group so later steps are not included in the loop. Report whole-session and final-set RPE, completion, fueling and the main limiting sensation to adjust subsequent training.

</details>

### See the result in Intervals.icu

![Intervals.icu calendar showing weeks 3–8 of the climbing and surges plan](docs/images/intervals-eight-week-calendar.png)

The screenshot shows **W3–W8** of the same plan, with the latest week at the top. Mondays and Fridays are clear for rest, Tuesdays contain climbing intervals, Thursdays contain surges, and weekends emphasize easy endurance. Weekly duration, TSS and PI appear on the left: **9h30m / 422 TSS / PI 2.66** for W7 and **8h30m / 357 TSS / PI 2.23** for W8.

Fitness and fatigue values on the left are platform projections from future scheduled training. They are not evidence that these workouts have been completed or a guarantee of improvement. Interpret the displayed PI using the proxy-boundary limitations above. The original screenshots use the Chinese interface; the explanation here covers their relevant values.

<a id="classification"></a>

## 1. Rider Classification

### Power-to-weight ratio: a template starting point

The default FTP power-to-weight heuristics below select a scaling template. They do not establish professional status or override training history, available time and recovery.

- **Full Pro · ≥4.5 W/kg:** retain more of the source workout structure, subject to training capacity and execution conditions.
- **Scaled · ≥3.2 and <4.5 W/kg:** reduce main-set volume and allow more recovery; candidate sessions commonly last 75–120 minutes.
- **Double-Scaled · <3.2 W/kg:** reduce main-set volume and high-intensity peaks further; candidate sessions commonly last 50–75 minutes.

Prefer a valid FTP when available. `CP20 × 0.95` is only an estimate, and CP60 also needs its testing protocol considered. CP1/FTP offers a short-duration power reference; it cannot diagnose W′, VLamax or muscle-fiber type. Other heuristic factors in the code need checking through repeatable testing.

### Other planning inputs

- **Goals and dates:** FTP, climbing, repeated surges, sprinting, long-ride durability or heat adaptation. Choose the primary goal before planning the phases.
- **Time and load:** recent actual training, longest ride, weekly TSS target/cap, daily availability and fixed rest days.
- **Intensity distribution:** polarized or pyramidal preferences and measured LT1/LT2. Label proxy assumptions when thresholds are unknown.
- **Strength and recovery:** leg training, sleep, soreness, heat and recent workout quality all affect recovery needs.
- **Age and setting:** adjust to experience and individual response; account for cooling and continuous pedaling indoors, and terrain, gearing and safety outdoors.

### Available workout structures

The base library includes low-intensity endurance, fast-start VO2, sustained threshold, Z3/Z4 with spikes, 2m/1m alternations and 30/30 micro-intervals. The [image-derived workout library](references/image-workouts.md) preserves source structure, terrain and unknowns before scaling.

The 80–85% FTP labels in older material must not automatically be treated as individual LT1 or low-intensity Z2. Establish individual thresholds and a consistent zone system before reporting distribution.

<a id="installation"></a>

## 2. Installation

### Recommended: interactive installation

```bash
npx skills add veibae37/pro_cycling_plan
```

Follow the installer's prompts to choose target tools and project/user scope. Then ask to “use pro-cycling-workouts,” or use your client's skill invocation method.

<details>
<summary><strong>View the installer</strong></summary>

![Skills installer discovering pro-cycling-workouts](docs/images/skills-installation.png)

This screen confirms that the repository was cloned and the skill discovered; installation still needs confirmation. It does not establish an Intervals.icu account connection.

</details>

### Manual installation and other environments

Keep the complete repository rather than copying only `SKILL.md`; the agent also needs `references/`, `scripts/`, `src/` and `mcp/`.

<details>
<summary><strong>Expand client-specific installation locations</strong></summary>

**Codex desktop / CLI / IDE extension**

```powershell
git clone https://github.com/veibae37/pro_cycling_plan.git "$env:USERPROFILE/.agents/skills/pro-cycling-workouts"
```

Use `~/.agents/skills/` for user scope or `.agents/skills/` inside the project for project scope. Invoke `$pro-cycling-workouts` or ask for the skill by name. If the destination already exists, update it rather than cloning over it. [Official skill documentation](https://learn.chatgpt.com/docs/build-skills)

**Claude Code**

Use `~/.claude/skills/pro-cycling-workouts/` for user scope or `.claude/skills/pro-cycling-workouts/` for project scope. Invoke `/pro-cycling-workouts` or ask in natural language. [Skills documentation](https://code.claude.com/docs/en/skills)

**Cursor / Windsurf / Cascade**

For Cursor, use a supported user skill directory or project-local `.cursor/skills/`. For Windsurf/Cascade, use the client's supported `.windsurf/skills/` or newer `.devin/skills/` location. Keep the native skill folder; do not rename `SKILL.md` to `.mdc`. [Cursor documentation](https://cursor.com/docs/skills) · [Cascade documentation](https://docs.devin.ai/desktop/cascade/skills)

**Gemini CLI**

```powershell
gemini skills install https://github.com/veibae37/pro_cycling_plan.git
gemini skills list --all
```

Configure MCP separately in the client's `mcpServers` settings. [Skills documentation](https://geminicli.com/docs/cli/skills/)

**Claude Projects / ChatGPT Projects / Custom GPTs**

Upload `SKILL.md`, the Markdown files in `references/`, `scripts/plan_metrics.py` and `src/tier_calculator.py`. Then use the [Claude adapter](adapters/claude-project-instructions.md) or [ChatGPT adapter](adapters/chatgpt-custom-gpt-prompt.md). Calculator execution depends on the client's code-execution capabilities.

Uploading files does not connect an account. Web environments need a supported remote MCP/plugin connection or tunnel. The base server in this repository offers local stdio only; uploading it does not make local client configuration available to a web project.

</details>

<a id="intervals-mcp"></a>

## 3. Connect Intervals.icu through MCP

### Prepare the account and runtime

1. Generate an API Key under Developer Settings in [Intervals.icu settings](https://intervals.icu/settings), and confirm your Athlete ID.
2. Create a Python virtual environment in the repository root and install dependencies compatible with the current `FastMCP` interface.
3. Merge the MCP entry into your client's private settings, start the connection, and test an account read first.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "mcp<2"
```

The base MCP server uses the standard library for HTTP requests. Install dependencies in the same Python environment used by the client's `command`. On macOS/Linux, use `.venv/bin/python` instead.

> [!IMPORTANT]
> Keep API Keys in private local configuration, never in chat, this README or Git. Account IDs and keys below are placeholders. Merge entries into existing MCP settings instead of replacing the entire file.

<details>
<summary><strong>Codex configuration: TOML</strong></summary>

Merge into your private user configuration at `~/.codex/config.toml`, replacing absolute paths and credentials:

```toml
[mcp_servers.intervals-icu]
command = "C:/path/to/pro_cycling_plan/.venv/Scripts/python.exe"
args = ["C:/path/to/pro_cycling_plan/mcp/intervals_mcp_server.py"]

[mcp_servers.intervals-icu.env]
INTERVALS_ATHLETE_ID = "i123456"
INTERVALS_API_KEY = "REPLACE_WITH_YOUR_API_KEY"
```

Restart the client and inspect the MCP connection, or run `codex mcp list`. [Official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

</details>

<details>
<summary><strong>Claude / Cursor / Cascade configuration: JSON</strong></summary>

Merge this entry into the client's supported `mcpServers` configuration:

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

In Claude Desktop, open Settings → Developer → Edit Config. Claude Code uses `.mcp.json` for project configuration. Cursor supports `~/.cursor/mcp.json` or project-local `.cursor/mcp.json`. Exclude credential-bearing project settings from Git. In Cascade, open MCP configuration from the client settings.

[Claude Code MCP](https://code.claude.com/docs/en/mcp) · [Cursor MCP](https://cursor.com/docs/mcp) · [Cascade MCP](https://docs.devin.ai/desktop/cascade/mcp)

</details>

### Base MCP tools

- **`get_athlete_profile()`**: read account details, weight and sport settings. Available FTP fields depend on the returned data.
- **`get_recent_wellness_and_activities(oldest_date, newest_date)`**: read activities and wellness within a date range. Interpret only returned metrics; they do not independently diagnose fatigue causes.
- **`create_intervals_workout(target_date, name, description_code, moving_time_sec)`**: write the prepared workout text to a calendar date. Pass the final duration in seconds; the default is 4,500 seconds.
- **`generate_and_push_pro_workout(...)`**: generate a fixed-model workout and immediately write it. Set `is_cp20=false` for FTP/CP60 input. This is not a preview tool and does not automatically adapt to recent wellness.

### Recommended workflow

**Read account and training history → Preview → Obtain write authorization → Check parsed steps and device sync.**

The base write tools use `POST /events` and do not implement calendar queries, updates, deletion or safe duplicate prevention. Check the calendar before retrying an ambiguous network result. A local MCP extension handled read-back and batch verification for the showcase; those operations are not part of these four base tools.

<details>
<summary><strong>Connection troubleshooting</strong></summary>

- **Missing `mcp.server` or `FastMCP`**: install `mcp<2` using the interpreter named in your configuration. The repository's `mcp/` folder is not the SDK.
- **Server will not start**: check interpreter/script paths, JSON/TOML syntax and client logs.
- **`Missing INTERVALS_API_KEY`**: confirm the key is passed through the server's `env`, then restart the connection.
- **HTTP 401/403**: check credentials and permissions, and whether network protection generated the response. A 403 does not necessarily mean the key is wrong.
- **Incomplete activity history**: API data-source restrictions or unsynced activities can leave gaps.
- **Calendar workout exists but the device has not received it**: inspect the platform's parsed steps, then verify the Garmin/Wahoo/Zwift integration separately.

</details>

<a id="usage"></a>

## 4. Usage & Maintenance

### Two calculation tools

- **`src/tier_calculator.py`**: select a fixed model using power-to-weight ratio and training conditions. See `--help`; use `--cp60` for FTP/CP60 and `--cp20` for CP20. `--weekly` produces a fixed weekly summary without writing to the calendar.
- **`scripts/plan_metrics.py`**: expand constant/range power steps and simple `Nx` loops into one-second targets to estimate duration, mechanical work, NP/TSS and optional three-zone PI. Use it to recalculate the showcase workout above.

Calculate `hours × (NP / FTP)² × 100` per session and sum the results for weekly TSS; average power is not a substitute for NP. Mechanical kJ is integrated from power and duration; kcal estimates require a stated efficiency assumption. When physiological thresholds are unknown, PI describes only an explicitly labeled proxy scenario.

### File guide

- [SKILL.md](SKILL.md): planning instructions, intake, output and feedback workflow.
- [Periodization](references/goal-periodization.md): goals, phases and reassessment.
- [Load and distribution](references/load-and-distribution.md): TSS, energy and PI calculation methods.
- [Image-derived workouts](references/image-workouts.md): source structure, terrain, scaling and ambiguities.
- [Feedback loop](references/feedback-loop.md): post-ride changes and session continuity.
- [Python calculator](src/tier_calculator.py), [metrics estimator](scripts/plan_metrics.py) and [base MCP server](mcp/intervals_mcp_server.py): implementation entry points.

Actual post-ride feedback can be stored in `.training-state/state.json` inside the training directory, which Git ignores. Without persistent storage, provide a copyable summary rather than claiming automatic memory across new chats. Updating a local plan does not update the calendar.

<a id="limits"></a>

### Implementation limits

- **Instructions and algorithms are separate:** editing `SKILL.md` does not change Python behavior. The agent plans target dates, race cycles, heat adaptation and custom sessions; the fixed CLI/MCP has no corresponding goal parameters.
- **Recheck fixed estimates:** the original calculator uses a fixed per-model IF for TSS/kJ, and some reported durations differ from expanded steps. Recalculate final workouts and inspect them in the platform.
- **Weekly summaries are not automatically adaptive:** fixed weekly schedules do not enforce every recovery, time, TSS or feedback constraint.
- **Some profile inputs are not exposed:** `RiderProfile` supports `sex`, but the current CLI/MCP generation interface uses its default value.
- **Metrics have limits:** the estimator is not an activity-file reader. Coasting, heat, actual sprints and individual thresholds affect real outcomes; TSS or PI alone cannot establish training quality.
- **Account setup is separate:** the base server provides local stdio only, without remote deployment, multi-user OAuth or device-sync verification. Skill installation alone does not demonstrate successful account access.

---

[简体中文](README.md) · **English**
