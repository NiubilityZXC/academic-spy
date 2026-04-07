# 学术间谍 / Academic Spy Skill

学术间谍（Academic Spy）是一个面向个人归档的 Canvas 导出 skill。

它的目标很直接：在学校账号、毕业生访问权限或课程可见性过期之前，尽可能把你自己仍有权限访问的学术信息完整导出下来，包括课程附件、作业说明、页面内容、公告、讨论、外链清单，以及页面里嵌入的 Canvas 文件。

Academic Spy is a reusable Canvas export skill for personal archiving.

Its goal is simple: before your school account, alumni access, or course visibility expires, download as much academic information as you can still legitimately access from your own account, including course files, assignment pages, announcements, discussions, external links, and embedded Canvas attachments.

## Skill 定位 / What This Skill Is

这不是一个“随便跑一下的脚本包”，而是一个可以被 Coding Agent 反复调用的 skill。

它把这件事拆成了稳定的几步：

- 连接你已经登录的 Edge 会话
- 导出 Canvas 标准附件和课程结构
- 补抓页面正文里嵌入的 Canvas 文件
- 生成校验报告，判断哪些是漏下的，哪些是课程侧已经失效的链接

This is not just a loose collection of scripts. It is meant to be used as an agent skill.

It turns the workflow into a repeatable sequence:

- Attach to an already logged-in Edge session
- Export standard Canvas files and course structure
- Recover Canvas files embedded inside saved content
- Produce verification reports to separate real gaps from stale course-side links

## 项目定位 / Scope

- 只复用你自己已经登录的 Edge 浏览器会话
- 只导出你当前账号本来就能访问到的内容
- 不绕过权限，不破解认证，不提升访问级别
- 更像“临期学术资料抢救导出 skill”而不是“通用爬虫平台”

- Reuses your own logged-in Edge session
- Exports only content your account can already access
- Does not bypass permissions, authentication, or access controls
- Optimized as an “archive before access expires” skill, not as a general scraping framework

## 功能 / Features

- 按课程名创建目录并归档资料
- 导出 Canvas Files API 能列出的标准附件
- 保存作业、页面、公告、讨论的 HTML、JSON 和文本内容
- 收集课程中的外部链接到 `external_links.txt`
- 从页面和作业正文里继续补抓嵌入的 Canvas 文件
- 生成校验报告，区分“本地没下到”和“Canvas 端死链接 / 404”

- Creates course-based folders automatically
- Exports standard attachments exposed by the Canvas Files API
- Saves assignments, pages, announcements, and discussions as HTML/JSON/text bundles
- Collects external links into `external_links.txt`
- Performs a second pass for Canvas file links embedded inside saved content
- Generates verification reports so you can separate local gaps from dead Canvas links

## 工作方式 / How It Works

这个 skill 通过 Microsoft Edge 的 Chrome DevTools Protocol 连接到真实浏览器，而不是重新实现登录流程。

如果你已经在 Edge 里登录了学校的 Canvas，它会直接复用当前会话；如果登录过期，它会等待你在打开的 Edge 窗口里重新完成登录。

This skill connects to a real Microsoft Edge session through the Chrome DevTools Protocol instead of rebuilding login flows.

If you are already signed into your school Canvas in Edge, it reuses that session. If the session expires, it pauses and waits for you to finish logging in again in the opened Edge window.

## 环境要求 / Requirements

- Windows
- Microsoft Edge
- Python 3.10+
- `websocket-client`

安装依赖 / Install dependency:

```powershell
pip install -r requirements.txt
```

## 快速开始 / Quick Start

如果你已经打开了学校的 Canvas，并且 Edge 里还是登录状态：

```powershell
python .\scripts\run_canvas_backup.py
```

If Canvas is already open in Edge and your session is still valid:

```powershell
python .\scripts\run_canvas_backup.py
```

如果没有自动识别到你的学校 Canvas 地址，先设置环境变量：

```powershell
$env:CANVAS_BASE = 'https://your-school.instructure.com'
$env:CANVAS_ROOT_DIR = 'D:\CanvasExport'
python .\scripts\run_canvas_backup.py
```

If your Canvas host cannot be auto-detected, set it explicitly first:

```powershell
$env:CANVAS_BASE = 'https://your-school.instructure.com'
$env:CANVAS_ROOT_DIR = 'D:\CanvasExport'
python .\scripts\run_canvas_backup.py
```

## 在 Agent 工具中使用 / Using This Skill In Agent Tools

### Codex

这是最直接的使用方式，因为仓库里已经包含了 `SKILL.md`。

把整个项目放进 Codex skill 目录，或让 Codex 在当前仓库中读取 `SKILL.md`。典型做法是：

```powershell
python .\scripts\run_canvas_backup.py
```

或者直接对 Codex 说：

```text
Use the Academic Spy skill in this repository to archive my Canvas courses from the currently logged-in Edge session.
```

### Claude Code

Claude Code 不一定原生支持 Codex 的 `SKILL.md` 机制，但可以把这个仓库当作“agent playbook + script bundle”使用。

推荐方式：

1. 让 Claude Code 打开这个仓库
2. 明确告诉它先读 `README.md` 和 `SKILL.md`
3. 再让它运行 `scripts/run_canvas_backup.py` 或指定的补抓脚本

示例提示词：

```text
Read README.md and SKILL.md in this repository, then use the provided scripts to archive my Canvas courses from my current Edge session.
```

### OpenClaw

如果 OpenClaw 支持仓库级提示或工作流文件，就把这个仓库直接作为任务工作区，并把 `README.md` / `SKILL.md` 作为操作规范。

如果它不支持 skill 元数据，也可以直接把它当成脚本化任务仓库：

```text
Use this repository as the workflow definition. Read README.md and SKILL.md first, then run the Canvas export and verification scripts.
```

### OpenCode

OpenCode 也可以按相同方式使用：把仓库作为上下文，先读 `README.md` 与 `SKILL.md`，再执行脚本。

推荐提示：

```text
Use the Academic Spy repository as a reusable skill. Read README.md and SKILL.md first, then run the export, supplement, and verification flow for my Canvas account.
```

### 兼容性说明 / Compatibility Note

- `Codex` 可以直接把它当 skill 使用
- `Claude Code / OpenClaw / OpenCode` 即使不支持 `SKILL.md` 原生触发，也可以把它当成“仓库化 skill”或“可执行 playbook”来用

- `Codex` can use it most directly as a skill
- `Claude Code / OpenClaw / OpenCode` can still use it as a repository-backed skill or executable playbook even if they do not natively support Codex skill triggering

## 常用命令 / Common Commands

全流程导出 / Full workflow:

```powershell
python .\scripts\run_canvas_backup.py
```

跳过完整导出，只补抓指定课程 / Skip full export and repair selected courses only:

```powershell
python .\scripts\run_canvas_backup.py --skip-export --course "Course A" --course "Course B"
```

只做校验 / Verification only:

```powershell
python .\scripts\canvas_verify.py
```

只补页面里的嵌入文件 / Embedded-file repair only:

```powershell
python .\scripts\run_canvas_embedded_supplement.py "Course A"
```

## 环境变量 / Environment Variables

- `CANVAS_BASE`
  Canvas 站点根地址，例如 `https://your-school.instructure.com`
- `CANVAS_ROOT_DIR`
  导出目录。默认是 `%USERPROFILE%\\Downloads\\canvas-export`
- `CANVAS_EDGE_EXE`
  Edge 可执行文件路径
- `CANVAS_EDGE_DEBUG_PORT`
  远程调试端口，默认 `9222`
- `CANVAS_EDGE_PROFILE_DIR`
  Edge profile 名称，默认 `Default`
- `CANVAS_COURSES_URL`
  可选，覆盖默认的 `Canvas Base + /courses`

- `CANVAS_BASE`
  Canvas root URL, for example `https://your-school.instructure.com`
- `CANVAS_ROOT_DIR`
  Export directory. Default: `%USERPROFILE%\\Downloads\\canvas-export`
- `CANVAS_EDGE_EXE`
  Edge executable path
- `CANVAS_EDGE_DEBUG_PORT`
  Remote debugging port, default `9222`
- `CANVAS_EDGE_PROFILE_DIR`
  Edge profile name, default `Default`
- `CANVAS_COURSES_URL`
  Optional override for the default `Canvas Base + /courses`

## 输出结果 / Outputs

主索引文件通常在：

- `_metadata/manifest.json`
- `_metadata/courses.json`
- `_metadata/verification_report.json`

每门课内部通常会包含：

- `Files/`
- `Assignments/`
- `Pages/`
- `Announcements/`
- `Discussions/`
- `external_links.txt`
- `_metadata/embedded_download_report.json`

Main index files usually appear in:

- `_metadata/manifest.json`
- `_metadata/courses.json`
- `_metadata/verification_report.json`

Each course directory usually contains:

- `Files/`
- `Assignments/`
- `Pages/`
- `Announcements/`
- `Discussions/`
- `external_links.txt`
- `_metadata/embedded_download_report.json`

## 校验逻辑 / Verification Semantics

- `standard_missing=0`
  表示 Canvas Files API 列出的标准附件都已经在本地找到
- `embedded_failed>0`
  表示页面正文里引用的某些 Canvas 文件仍然下载失败
- `unaccounted_referenced_ids>0`
  表示页面里还有文件 ID 被引用，但既不在标准附件里，也不在嵌入文件报告里

- `standard_missing=0`
  Means every standard attachment listed by the Canvas Files API was found locally
- `embedded_failed>0`
  Means some Canvas file links embedded in saved content still failed to download
- `unaccounted_referenced_ids>0`
  Means saved content still references Canvas file IDs not covered by the standard export or embedded report

如果某个剩余链接最终在 Canvas 页面上返回 `404` 或 `Page Not Found`，通常应该把它视为课程里的失效旧链接，而不是本地脚本遗漏。

If a remaining link resolves to Canvas `404` or `Page Not Found`, it should usually be treated as a stale course-side link rather than a local export bug.

## 项目结构 / Project Structure

```text
academic-spy/
  README.md
  SKILL.md
  requirements.txt
  .gitignore
  scripts/
    run_canvas_backup.py
    run_canvas_export.py
    run_canvas_deep_supplement.py
    run_canvas_embedded_supplement.py
    canvas_export.py
    canvas_deep_supplement.py
    canvas_embedded_supplement.py
    canvas_runtime.py
    canvas_verify.py
```

## 说明 / Notes

这个仓库首先是一个 skill，其次才是一个脚本项目。`SKILL.md` 定义的是 agent 应该如何理解和调用这套流程；`scripts/` 目录则提供了真正执行工作的实现。

The repository is first and foremost a skill, and secondarily a script project. `SKILL.md` defines how an agent should understand and invoke the workflow, while `scripts/` contains the actual implementation.

这个仓库里的 Codex skill 名称仍然是 `canvas-course-archive`，因为这个名字更适合触发和复用；项目标题则使用“学术间谍 / Academic Spy Skill”。

The bundled Codex skill still uses the internal name `canvas-course-archive` because it is more descriptive for triggering and reuse; the public-facing project title is “Academic Spy Skill”.
