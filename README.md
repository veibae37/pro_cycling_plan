![Pixel-art cyclists climbing a mountain road](docs/images/pro-cycling-banner.jpg)

# Pro Cycling Plan & Workouts

**目标导向排课 · 职业课表缩放 · 负荷核算 · Intervals.icu MCP**

Adaptive cycling plans built around your goals, available time and recovery, with reusable Agent Skills, a local calculator and optional Intervals.icu integration.

从 FTP、爬坡到反复拉扯与长距离耐受：先确定目标与约束，再安排周期、选择课表，并根据骑后反馈调整。

[查看演示](#showcase) · [骑手分类](#classification) · [安装技能](#installation) · [连接 Intervals.icu](#intervals-mcp) · [计算与维护](#usage)

> [!NOTE]
> 本仓库包含三个独立部分：`SKILL.md` 排课规则、Python 计算器、Intervals.icu MCP。安装 Skill 不会自动连接账号；多周规划由 Agent 按规则编排，固定计算器的能力见[实现边界](#limits)。

<a id="showcase"></a>

## Showcase / 从一句输入到八周训练日历

**输入目标 → 编排周期 → 核算负荷 → 授权导入 → 骑后调整**

### 你的输入

> 使用 pro-cycling-workouts：体重70 kg、FTP 200 W，想提高爬坡和反复拉扯能力，无力量训练。从2026年11月开始安排8周极化训练，PI希望高于1.5。每周最多10小时，周一、周五休息，最长单次3小时，周TSS在350–450之间。请生成课表并通过MCP写入Intervals.icu。

### 得到的计划

**8 周 · 40 节训练 · 每周 8.5–9.5 小时 · 周 TSS 355–422**

- **骑手画像**：FTP **200 W / 2.86 W/kg**，按当前训练史、时间预算和恢复缩放课表。
- **训练结构**：周二爬坡间歇，周四受控拉扯；周三、周六安排低强度缓坡与耐力，周日为可删减的轻松骑。
- **周期推进**：前3周渐进构建，第4周减少高强度；第5–7周增加专项容量，第8周恢复并比较同协议主组完成质量。
- **实际交付**：40节结构化训练已导入并读回核对，日期、功率、展开后的间歇与恢复次数、时长一致。设备端同步需另行验证。

<details>
<summary><strong>展开八周负荷与强度分布</strong></summary>

周期为 **2026-11-02 至 2026-12-27**，时区为 Asia/Singapore。下面的 TSS 为平台读回值，PI 为目标功率下的代理估计。

- **W1 · 11/02–11/08**：8h30m，**358 TSS**，PI **2.29**；从3×2分钟爬坡主组起步。
- **W2 · 11/09–11/15**：8h50m，**379 TSS**，PI **2.43**；延长为3×3分钟。
- **W3 · 11/16–11/22**：9h15m，**402 TSS**，PI **2.53**；增加为4×3分钟。
- **W4 · 11/23–11/29**：8h30m，**355 TSS**，PI **2.09**；减少高强度容量，检查恢复。
- **W5 · 11/30–12/06**：9h15m，**402 TSS**，PI **2.53**；恢复后回到4×3分钟。
- **W6 · 12/07–12/13**：9h30m，**420 TSS**，PI **2.64**；延长为4×4分钟。
- **W7 · 12/14–12/20**：9h30m，**422 TSS**，PI **2.66**；增加受控拉扯重复次数。
- **W8 · 12/21–12/27**：8h30m，**357 TSS**，PI **2.23**；减少高强度，重复首周主组比较完成质量。

三强度区暂用 **70% / 100% FTP（140 / 200 W）** 作代理边界，低区时间占多数且高区多于中区；这不是实测 LT1/LT2，也不能把普通 FTP 七区直接当作三生理强度区。按功率统计的短间歇时间不等于实际高摄氧或高心率时间。

恢复周保留较多低强度时间，是350 TSS下限要求下的折中。此案例不适用于所有骑手；明显疲劳时应减课，允许低于目标，不追补TSS。

</details>

<details>
<summary><strong>展开代表课：60 分钟爬坡间歇 · 约 51 TSS · 460 kJ</strong></summary>

首周周二主组为 **3×2分钟220 W**，两次组间恢复各4分钟100 W。选择安全连续坡或骑行台，不强制低踏频大扭矩。

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

时长为 `15 + 6 + 8 + 21 + 10 = 60 min`。按FTP 200 W计算，计划NP约 **142.5 W**、TSS **50.77**、机械做功 **459.6 kJ**；假设机械效率20–25%，骑行消耗粗估 **439–549 kcal**。

骑中碳水可从已耐受的40–50 g/h起步，按胃肠反应调整；补水按环境与个人出汗量安排。热身明显比平时吃力时可缩短或休息。

[下载训练文本](examples/climbing-surges-60m.txt) · [查看核算口径](references/load-and-distribution.md)

```powershell
python -X utf8 scripts/plan_metrics.py --workout examples/climbing-surges-60m.txt --ftp 200
```

保留循环后的空行，避免后续步骤被卷入重复组。骑后反馈全课/末组RPE、完成情况、补给与主要限制感，即可修订后续训练。

</details>

### 在 Intervals.icu 中查看结果

![Intervals.icu calendar showing weeks 3–8 of the climbing and surges plan](docs/images/intervals-eight-week-calendar.png)

截图展示同一计划的 **W3–W8**，最新周在上方：周一、周五留空休息，周二为爬坡间歇，周四为拉扯训练，周末以低强度耐力为主。左侧可核对周时长、TSS与PI；例如W7为 **9h30m / 422 TSS / PI 2.66**，W8为 **8h30m / 357 TSS / PI 2.23**。

左侧健康度、疲劳等数值为平台对未来已排训练的推算，不代表这些训练已经完成或保证带来相应提升。截图中的PI也应结合上述代理阈值理解。

<a id="classification"></a>

## 1. Classification / 骑手分类

### 功体比：模板起点

默认FTP功体比启发式分档如下。档位用于选择缩放模板，不代表职业水平，也不能覆盖训练史、时间预算与恢复。

- **Full Pro · ≥4.5 W/kg**：保留较完整的职业课表结构，仍需确认训练容量与执行条件。
- **Scaled · ≥3.2 且 <4.5 W/kg**：减少主组容量、适当延长恢复，常用75–120分钟候选课。
- **Double-Scaled · <3.2 W/kg**：进一步减少主组容量和高强度峰值，常用50–75分钟候选课。

有有效FTP时优先使用；`CP20 × 0.95` 仅是估计，CP60也应结合测试协议理解。CP1/FTP只作短时功率倾向参考，不能诊断W′、VLamax或肌纤维类型。代码中的其他启发式系数需通过一致协议复测校核。

### 还要考虑哪些条件

- **目标与日期**：FTP、爬坡、反复提速、冲刺、长骑耐受或热适应；先选主要目标，再倒排阶段。
- **周时间与负荷**：近期真实骑行量、最长骑行、周TSS目标/上限、每日可用时长与固定休息日。
- **强度分布**：极化或金字塔偏好，以及实测LT1/LT2；没有阈值时明确标注代理假设。
- **力量与恢复**：腿部力量训练、睡眠、酸痛、热环境与最近完成质量都占恢复预算。
- **年龄与场景**：结合训练经历与个人反应调整；室内考虑散热和连续踩踏，户外考虑地形、齿比和安全。

### 可选课表结构

基础库包含低强度耐力、快启VO2、持续阈值、Z3/Z4与Spikes、2m/1m交替、30/30微间歇等结构。另有[图片课表库](references/image-workouts.md)，用于保留原训练结构、地形和未知项后再缩放。

旧材料中的80–85%FTP不能直接认定为个人LT1或低强度Z2；采用个人阈值和统一分区后再统计分布。

<a id="installation"></a>

## 2. Installation / 安装技能

### 推荐：交互式安装

```bash
npx skills add veibae37/pro_cycling_plan
```

按安装器提示选择目标工具与项目/用户范围。安装后直接说“使用 pro-cycling-workouts”，或使用客户端支持的技能调用方式。

<details>
<summary><strong>查看安装界面</strong></summary>

![Skills installer discovering pro-cycling-workouts](docs/images/skills-installation.png)

该界面表示仓库已克隆、技能已识别；之后仍需确认安装。它不代表Intervals.icu账号已经连接。

</details>

### 手动安装与其他环境

保留完整仓库，不要只复制`SKILL.md`；Agent还需要访问`references/`、`scripts/`、`src/`和`mcp/`。

<details>
<summary><strong>展开各客户端安装位置</strong></summary>

**Codex desktop / CLI / IDE extension**

```powershell
git clone https://github.com/veibae37/pro_cycling_plan.git "$env:USERPROFILE/.agents/skills/pro-cycling-workouts"
```

个人范围使用`~/.agents/skills/`；项目范围使用项目内的`.agents/skills/`。调用`$pro-cycling-workouts`或直接说明要使用该技能。目标目录已存在时更新原目录，不覆盖克隆。[官方技能文档](https://learn.chatgpt.com/docs/build-skills)

**Claude Code**

个人范围使用`~/.claude/skills/pro-cycling-workouts/`，项目范围使用`.claude/skills/pro-cycling-workouts/`。通过`/pro-cycling-workouts`或自然语言调用。[技能文档](https://code.claude.com/docs/en/skills)

**Cursor / Windsurf / Cascade**

Cursor使用其支持的用户技能目录或项目内`.cursor/skills/`；Windsurf/Cascade使用客户端支持的`.windsurf/skills/`或新版`.devin/skills/`。使用原生技能文件夹，不把`SKILL.md`改名为`.mdc`。[Cursor文档](https://cursor.com/docs/skills) · [Cascade文档](https://docs.devin.ai/desktop/cascade/skills)

**Gemini CLI**

```powershell
gemini skills install https://github.com/veibae37/pro_cycling_plan.git
gemini skills list --all
```

MCP在客户端的`mcpServers`中另外配置。[技能文档](https://geminicli.com/docs/cli/skills/)

**Claude Projects / ChatGPT Projects / Custom GPTs**

上传`SKILL.md`、`references/`中的Markdown、`scripts/plan_metrics.py`及`src/tier_calculator.py`，再使用[Claude适配指令](adapters/claude-project-instructions.md)或[ChatGPT适配指令](adapters/chatgpt-custom-gpt-prompt.md)。能否运行计算器取决于客户端的代码执行能力。

上传文件不会连接账号。网页环境需要受支持的远程MCP/插件连接或隧道；本仓库基础服务仅提供本地stdio，不会读取网页项目之外的本机配置。

</details>

<a id="intervals-mcp"></a>

## 3. Intervals.icu MCP / 连接训练日历

### 准备账号与运行环境

1. 在[Intervals.icu设置](https://intervals.icu/settings)的Developer Settings中生成API Key，并确认Athlete ID。
2. 在仓库根目录创建Python虚拟环境，安装与当前`FastMCP`接口兼容的依赖。
3. 把MCP配置合并到客户端的私人设置中，再启动连接并先测试账号读取。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "mcp<2"
```

本仓库基础MCP使用标准库发送HTTP请求。依赖必须装在客户端`command`使用的Python环境中；macOS/Linux请改用`.venv/bin/python`。

> [!IMPORTANT]
> API Key只保存在私人本地配置中，不要发到聊天、README或Git仓库。下列账号与密钥均为占位符。现有MCP设置应合并保留，不要整文件覆盖。

<details>
<summary><strong>Codex 配置：TOML</strong></summary>

合并到私人用户配置`~/.codex/config.toml`，替换绝对路径和凭据：

```toml
[mcp_servers.intervals-icu]
command = "C:/path/to/pro_cycling_plan/.venv/Scripts/python.exe"
args = ["C:/path/to/pro_cycling_plan/mcp/intervals_mcp_server.py"]

[mcp_servers.intervals-icu.env]
INTERVALS_ATHLETE_ID = "i123456"
INTERVALS_API_KEY = "REPLACE_WITH_YOUR_API_KEY"
```

重启客户端后检查MCP连接，或运行`codex mcp list`。[官方MCP文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

</details>

<details>
<summary><strong>Claude / Cursor / Cascade 配置：JSON</strong></summary>

把条目合并到客户端支持的`mcpServers`配置中：

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

Claude Desktop可从Settings → Developer → Edit Config打开配置；Claude Code项目配置为`.mcp.json`；Cursor支持`~/.cursor/mcp.json`或项目内`.cursor/mcp.json`。含凭据的项目配置应排除在Git之外。Cascade请从客户端设置中打开MCP配置。

[Claude Code MCP](https://code.claude.com/docs/en/mcp) · [Cursor MCP](https://cursor.com/docs/mcp) · [Cascade MCP](https://docs.devin.ai/desktop/cascade/mcp)

</details>

### 基础 MCP 工具

- **`get_athlete_profile()`**：读取账号、体重与运动设置。FTP相关字段取决于实际返回数据。
- **`get_recent_wellness_and_activities(oldest_date, newest_date)`**：读取日期范围内的活动与wellness；只解释实际返回指标，不据此单独诊断疲劳原因。
- **`create_intervals_workout(target_date, name, description_code, moving_time_sec)`**：把已编排的训练文本写入指定日期。必须传最终秒数，默认值为4500秒。
- **`generate_and_push_pro_workout(...)`**：用固定模型生成并立即写入。输入FTP/CP60时设`is_cp20=false`；它不是预览工具，也不会自动结合近期wellness调整课表。

### 推荐流程

**读取账号与训练史 → 预览课表 → 用户授权写入 → 核对解析与设备同步。**

基础服务的写入工具使用`POST /events`，未实现日历查询、更新、删除或安全去重。网络结果不明时先查日历，不盲目重试。上方演示的回读与批量核对由本地MCP扩展完成，不属于这四个基础工具。

<details>
<summary><strong>常见连接问题</strong></summary>

- **缺少`mcp.server`或`FastMCP`**：使用配置中同一个Python解释器安装`mcp<2`。找到仓库的`mcp/`目录不代表SDK已安装。
- **进程无法启动**：检查解释器、脚本绝对路径、JSON/TOML语法与客户端日志。
- **`Missing INTERVALS_API_KEY`**：确认密钥通过服务的`env`传入，再重启连接。
- **HTTP 401/403**：核对凭据与权限，并检查响应是否来自网络防护；403不一定代表密钥错误。
- **缺少部分历史活动**：API数据源限制或未同步活动可能使历史不完整。
- **日历已有训练但设备没有收到**：检查平台解析出的步骤，再验证Garmin/Wahoo/Zwift等设备集成。

</details>

<a id="usage"></a>

## 4. Usage & Maintenance / 计算与维护

### 两种计算工具

- **`src/tier_calculator.py`**：按功体比与训练条件选择固定模型。参数见`--help`；使用FTP/CP60时传`--cp60`，CP20传`--cp20`。`--weekly`输出固定周摘要，不会写日历。
- **`scripts/plan_metrics.py`**：对常数/范围功率段和简单`Nx`循环逐秒估算时长、机械做功、NP/TSS及可选三强度区PI。上方唯一演示的代表课可用其复算。

TSS按每课`hours × (NP / FTP)² × 100`计算后相加，不用平均功率代替NP。kJ由功率与时长积分；kcal应声明机械效率假设。生理阈值未知时，PI仅能作为明确代理情景的估计。

### 文件导航

- [SKILL.md](SKILL.md)：排课规则、目标采集、输出与反馈流程。
- [周期化规划](references/goal-periodization.md)：目标、阶段与复测安排。
- [负荷与分布](references/load-and-distribution.md)：TSS、能量与PI计算口径。
- [图片课表库](references/image-workouts.md)：来源结构、地形、缩放与歧义。
- [反馈循环](references/feedback-loop.md)：训练后调整与续接规则。
- [Python计算器](src/tier_calculator.py)、[指标估算器](scripts/plan_metrics.py)、[基础MCP服务](mcp/intervals_mcp_server.py)：各自的实现入口。

真实骑后反馈可保存在训练目录的`.training-state/state.json`，该目录已被Git忽略。没有持久存储时提供可复制摘要，不声称跨新聊天自动记住；本地改计划不等于日历已经更新。

<a id="limits"></a>

### 实现边界

- **规则不等于算法**：修改`SKILL.md`不会改变Python代码；目标日期、比赛周期、热适应和自定义专项由Agent编排，固定CLI/MCP没有这些目标参数。
- **固定估算需复核**：原计算器使用每模型固定IF估算TSS/kJ，部分报告时长与展开步骤不同；最终课表应逐段核算并在平台检查。
- **周摘要不自动自适应**：固定周表不会自动执行所有恢复、周时间、TSS或反馈约束。
- **部分画像参数未暴露**：`RiderProfile`支持`sex`，当前CLI/MCP生成接口仍使用默认值。
- **指标有适用范围**：指标估算器不是活动文件读取器；滑行、热环境、真实冲刺和个体阈值会改变实绩，不能只靠TSS或PI判定训练质量。
- **账号连接独立配置**：基础MCP仅提供本地stdio，没有远程部署、多用户OAuth或设备同步验证；安装技能本身不能证明账号读写成功。
