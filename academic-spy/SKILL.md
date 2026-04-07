---
name: canvas-course-archive
description: Use when the user wants to archive Canvas courses from a logged-in Microsoft Edge session, download files and page-linked attachments by course, and verify what is still missing or dead on the Canvas side.
---

# Canvas Course Archive

This skill packages the Canvas export workflow used to back up course materials into per-course folders.

It is designed for Windows and Microsoft Edge. The scripts attach to a real Edge profile through the Chrome DevTools Protocol so they can reuse the current Canvas login.

## Use this skill for

- Full-course Canvas exports
- Re-running missing downloads after partial failures
- Pulling embedded file links from assignments and pages
- Verifying whether remaining misses are true gaps or dead Canvas links

## Script layout

- `scripts/run_canvas_backup.py`
  Main entry point. Runs export, supplement, and verification in order.
- `scripts/run_canvas_export.py`
  Wrapper for the full Canvas export.
- `scripts/run_canvas_deep_supplement.py`
  Repairs missing standard files and resolves embedded file metadata.
- `scripts/run_canvas_embedded_supplement.py`
  Downloads embedded Canvas files referenced from saved HTML and JSON.
- `scripts/canvas_verify.py`
  Produces `_metadata/verification_report.json`.

The copied low-level modules in `scripts/canvas_export.py`, `scripts/canvas_deep_supplement.py`, and `scripts/canvas_embedded_supplement.py` are internal implementation files. Prefer the `run_*.py` wrappers.

## Environment

Set these when auto-detection is not enough:

```powershell
$env:CANVAS_BASE = 'https://your-school.instructure.com'
$env:CANVAS_ROOT_DIR = 'D:\CanvasExport'
$env:CANVAS_EDGE_EXE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$env:CANVAS_EDGE_DEBUG_PORT = '9222'
$env:CANVAS_EDGE_PROFILE_DIR = 'Default'
```

Default behavior:

- Canvas host: auto-detected from an open Canvas tab when possible
- Export root: `%USERPROFILE%\Downloads\canvas-export`
- Edge debug port: `9222`
- Edge profile: `Default`

If there is no open Canvas tab and `CANVAS_BASE` is unset, the scripts can still open Edge with remote debugging, but you should set `CANVAS_BASE` first so the workflow knows which Canvas site to target.

## Recommended commands

Full run:

```powershell
python "$env:CODEX_HOME\skills\canvas-course-archive\scripts\run_canvas_backup.py"
```

Supplement selected courses only:

```powershell
python "$env:CODEX_HOME\skills\canvas-course-archive\scripts\run_canvas_backup.py" --skip-export --course "Course A" --course "Course B"
```

Verification only:

```powershell
python "$env:CODEX_HOME\skills\canvas-course-archive\scripts\canvas_verify.py"
```

Embedded-only repair:

```powershell
python "$env:CODEX_HOME\skills\canvas-course-archive\scripts\run_canvas_embedded_supplement.py" "Course A"
```

## Expected outputs

- `<CANVAS_ROOT_DIR>\_metadata\manifest.json`
- `<CANVAS_ROOT_DIR>\_metadata\courses.json`
- `<CANVAS_ROOT_DIR>\_metadata\verification_report.json`
- `<course>\_metadata\embedded_download_report.json`
- `<course>\external_links.txt`

## Interpretation

- `standard_missing=0` means every file listed by the Canvas Files API exists locally in the expected course folder.
- `embedded_failed>0` means at least one file ID referenced from saved content still failed to download.
- `unaccounted_referenced_ids>0` means saved content references Canvas file IDs that are not covered by the standard file export or embedded report.
- If a remaining link resolves to Canvas `404` or `Page Not Found`, treat it as a dead course link rather than a local export bug.

## Guardrails

- Reuse the existing logged-in Edge profile whenever possible.
- If the login expires, let the script pause and wait for the user to finish the Canvas login in Edge.
- Do not claim completion before running `scripts/canvas_verify.py`.
- Prefer targeted supplement reruns before deleting or rebuilding an export directory.
