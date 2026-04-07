# 学术间谍 / Academic Spy skill

学术间谍（Academic Spy）是一个面向个人归档的 Canvas 导出项目。

它的目标很直接：在学校账号、毕业生访问权限或课程可见性过期之前，尽可能把你自己仍有权限访问的学术信息完整导出下来，包括课程附件、作业说明、页面内容、公告、讨论、外链清单，以及页面里嵌入的 Canvas 文件。

Academic Spy is a personal archival toolkit for Canvas.

Its goal is simple: before your school account, alumni access, or course visibility expires, download as much academic information as you can still legitimately access from your own account, including course files, assignment pages, announcements, discussions, external links, and embedded Canvas attachments.

## 项目定位 / Scope

- 只复用你自己已经登录的 Edge 浏览器会话
- 只导出你当前账号本来就能访问到的内容
- 不绕过权限，不破解认证，不提升访问级别
- 更像“临期学术资料抢救导出”而不是“通用爬虫平台”

- Reuses your own logged-in Edge session
- Exports only content your account can already access
- Does not bypass permissions, authentication, or access controls
- Optimized for “archive before access expires,” not for broad scraping

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

这个项目通过 Microsoft Edge 的 Chrome DevTools Protocol 连接到真实浏览器，而不是重新实现登录流程。

如果你已经在 Edge 里登录了学校的 Canvas，它会直接复用当前会话；如果登录过期，它会等待你在打开的 Edge 窗口里重新完成登录。

This project connects to a real Microsoft Edge session through the Chrome DevTools Protocol instead of rebuilding login flows.

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

这个仓库里的 Codex skill 名称仍然是 `canvas-course-archive`，因为这个名字更适合触发和复用；项目标题则使用“学术间谍 / Academic Spy”。

The bundled Codex skill still uses the internal name `canvas-course-archive` because it is more descriptive for triggering and reuse; the public-facing project title is “学术间谍 / Academic Spy”.
