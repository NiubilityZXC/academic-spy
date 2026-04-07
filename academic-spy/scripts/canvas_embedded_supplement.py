import json
import sys
import time
from pathlib import Path

import canvas_export as ce
from canvas_deep_supplement import FILE_LINK_RE, TEXT_SUFFIXES, load_json


REPORT_NAME = "embedded_download_report.json"
SELF_GENERATED_METADATA = {"embedded_files.json", REPORT_NAME}


def course_dirs(selected_names=None):
    paths = [path for path in sorted(ce.ROOT_DIR.iterdir()) if path.is_dir() and not path.name.startswith("_")]
    if not selected_names:
        return paths
    by_name = {path.name: path for path in paths}
    ordered = [by_name[name] for name in selected_names if name in by_name]
    return ordered


def collect_embedded_ids(course_dir: Path):
    file_ids = set()
    for path in course_dir.rglob("*"):
        if not path.is_file():
            continue
        if "Files" in path.parts:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.name in SELF_GENERATED_METADATA:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in FILE_LINK_RE.finditer(text):
            file_ids.add(int(match.group(2)))
    return sorted(file_ids)


def standard_file_ids(course_dir: Path):
    items = load_json(course_dir / "_metadata" / "files.json", [])
    return {int(item["id"]) for item in items if isinstance(item, dict) and item.get("id") is not None}


def report_path(course_dir: Path):
    return course_dir / "_metadata" / REPORT_NAME


def load_report(course_dir: Path):
    raw = load_json(report_path(course_dir), {})
    if isinstance(raw, list):
        by_id = {}
        for item in raw:
            if isinstance(item, dict) and item.get("file_id") is not None:
                by_id[str(item["file_id"])] = item
        return by_id
    if isinstance(raw, dict):
        return raw
    return {}


def save_report(course_dir: Path, report: dict):
    ordered = dict(sorted(report.items(), key=lambda item: int(item[0])))
    ce.save_json(report_path(course_dir), ordered)


def load_embedded_metadata(course_dir: Path):
    items = load_json(course_dir / "_metadata" / "embedded_files.json", [])
    return {int(item["id"]): item for item in items if isinstance(item, dict) and item.get("id") is not None}


def clear_dir(path: Path):
    ce.ensure_dir(path)
    for item in path.iterdir():
        if item.is_file():
            try:
                item.unlink()
            except Exception:
                pass


def wait_for_download(temp_dir: Path, timeout: int = 180):
    deadline = time.time() + timeout
    stable = {}
    while time.time() < deadline:
        partials = [p for p in temp_dir.iterdir() if p.is_file() and p.suffix.lower() == ".crdownload"]
        finished = [p for p in temp_dir.iterdir() if p.is_file() and p.suffix.lower() != ".crdownload"]
        if finished and not partials:
            finished.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            candidate = finished[0]
            size = candidate.stat().st_size
            previous = stable.get(candidate.name)
            if previous == size and size > 0:
                return candidate
            stable[candidate.name] = size
        time.sleep(1)
    return None


def fallback_target(course_dir: Path, file_id: int, metadata: dict | None):
    name = None
    if metadata:
        name = metadata.get("display_name") or metadata.get("filename")
    if not name:
        name = f"file_{file_id}"
    return course_dir / "Files" / "_embedded_from_pages" / ce.sanitize_name(name)


def expected_size(metadata: dict | None):
    if not metadata:
        return None
    value = metadata.get("size")
    return value if isinstance(value, int) and value > 0 else None


def browser_download(url: str, temp_dir: Path, timeout: int = 180):
    clear_dir(temp_dir)
    target = ce.create_aux_target("about:blank")
    cdp = ce.CDPClient(target["webSocketDebuggerUrl"])
    try:
        cdp.call("Page.enable")
        try:
            cdp.call("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(temp_dir)})
        except Exception:
            pass
        cdp.call("Page.navigate", {"url": url})
        downloaded = wait_for_download(temp_dir, timeout=timeout)
        if downloaded:
            return downloaded
        try:
            location = ce.evaluate(cdp, "location.href")
        except Exception:
            location = url
        raise RuntimeError(f"download did not complete; final location={location}")
    finally:
        cdp.close()
        ce.close_target(target["id"])


def move_download(downloaded: Path, target: Path):
    ce.ensure_dir(target.parent)
    final_target = target
    if final_target.exists():
        if final_target.stat().st_size == downloaded.stat().st_size:
            downloaded.unlink()
            return final_target
        final_target = ce.ensure_unique_file(final_target)
    downloaded.replace(final_target)
    return final_target


def download_embedded(course_dir: Path, file_id: int, metadata: dict | None, report: dict):
    entry = report.get(str(file_id), {})
    recorded_path = entry.get("path")
    if recorded_path:
        recorded_file = Path(recorded_path)
        recorded_size = entry.get("size")
        if recorded_file.exists() and (not recorded_size or recorded_file.stat().st_size == recorded_size):
            return "already_downloaded", recorded_file

    download_url = None
    if metadata:
        download_url = metadata.get("url")
    if not download_url:
        download_url = f"{ce.CANVAS_BASE}/files/{file_id}/download?download_frd=1"

    temp_dir = ce.DOWNLOAD_TMP_DIR / f"embedded_{file_id}"
    expected = expected_size(metadata)
    timeout = 90
    if expected and expected > 100 * 1024 * 1024:
        timeout = 600
    elif expected and expected > 20 * 1024 * 1024:
        timeout = 180
    if entry.get("status") == "failed":
        timeout = min(timeout, 45)
    target = fallback_target(course_dir, file_id, metadata)
    if metadata:
        preferred_name = metadata.get("display_name") or metadata.get("filename")
        if preferred_name:
            target = target.with_name(ce.sanitize_name(preferred_name))

    try:
        downloaded = browser_download(download_url, temp_dir, timeout=timeout)
        if not metadata:
            target = target.with_name(ce.sanitize_name(downloaded.name))
        final_target = move_download(downloaded, target)
    except Exception as browser_exc:
        try:
            ce.download_file_via_browser(download_url, target, expected)
            final_target = target
        except Exception:
            raise browser_exc

    size = final_target.stat().st_size if final_target.exists() else None
    status = "downloaded"
    if expected and size != expected:
        status = "size_mismatch"

    report[str(file_id)] = {
        "file_id": file_id,
        "status": status,
        "path": str(final_target),
        "name": final_target.name,
        "size": size,
        "expected_size": expected,
        "url": download_url,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return status, final_target


def main(selected_names=None):
    ce.start_edge_if_needed()
    page = ce.CDPClient(ce.get_or_create_canvas_target()["webSocketDebuggerUrl"])
    try:
        ce.wait_for_canvas_login(page)
    finally:
        page.close()

    total_candidates = 0
    total_downloaded = 0
    total_failed = 0

    for course_dir in course_dirs(selected_names):
        api_ids = standard_file_ids(course_dir)
        embedded_ids = [file_id for file_id in collect_embedded_ids(course_dir) if file_id not in api_ids]
        metadata_by_id = load_embedded_metadata(course_dir)
        report = load_report(course_dir)

        ce.log(f"{course_dir.name}: embedded_candidates={len(embedded_ids)}")
        total_candidates += len(embedded_ids)

        for file_id in embedded_ids:
            metadata = metadata_by_id.get(file_id)
            try:
                status, target = download_embedded(course_dir, file_id, metadata, report)
                save_report(course_dir, report)
                if status in {"downloaded", "size_mismatch"}:
                    total_downloaded += 1
                ce.log(f"{course_dir.name}: {file_id} -> {status} -> {target.name}")
            except Exception as exc:
                total_failed += 1
                report[str(file_id)] = {
                    "file_id": file_id,
                    "status": "failed",
                    "error": str(exc),
                    "url": metadata.get("url") if metadata else f"{ce.CANVAS_BASE}/files/{file_id}/download?download_frd=1",
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                save_report(course_dir, report)
                ce.log(f"{course_dir.name}: {file_id} failed ({exc})")

    ce.log(
        "Embedded supplement finished. "
        f"Candidates={total_candidates}. "
        f"Downloaded_this_run={total_downloaded}. "
        f"Failed_this_run={total_failed}."
    )


if __name__ == "__main__":
    main(sys.argv[1:] or None)
