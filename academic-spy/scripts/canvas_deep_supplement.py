import json
import re
import time
from collections import defaultdict
from pathlib import Path

import canvas_export as ce


TEXT_SUFFIXES = {".html", ".txt", ".json"}
FILE_LINK_RE = re.compile(r"(?:https?://[^/]+)?(?:/api/v1)?/courses/(\d+)/files/(\d+)", re.I)


def current_disk_index(files_root: Path):
    index = defaultdict(list)
    if not files_root.exists():
        return index
    for path in files_root.rglob("*"):
        if path.is_file():
            index[path.name].append(path.stat().st_size)
    return index


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def collect_standard_missing(course_dir: Path):
    files_json_path = course_dir / "_metadata" / "files.json"
    folders_json_path = course_dir / "_metadata" / "folders.json"
    items = load_json(files_json_path, [])
    folders = load_json(folders_json_path, [])
    folder_by_id = {folder["id"]: folder for folder in folders if isinstance(folder, dict) and folder.get("id") is not None}
    disk = current_disk_index(course_dir / "Files")
    missing = []
    for item in items:
        name = item.get("display_name") or item.get("filename") or f"file_{item['id']}"
        size = item.get("size")
        if size in disk.get(name, []):
            continue
        folder = folder_by_id.get(item.get("folder_id"))
        rel_folder = ce.safe_rel_folder(folder.get("full_name") if folder else "")
        target = course_dir / "Files" / rel_folder / ce.sanitize_name(name)
        missing.append(
            {
                "kind": "files_api",
                "file_id": item.get("id"),
                "name": name,
                "size": size,
                "url": item["url"],
                "target": target,
            }
        )
    return missing


def collect_embedded_file_ids(course_dir: Path):
    file_ids = set()
    for path in course_dir.rglob("*"):
        if not path.is_file():
            continue
        if "Files" in path.parts:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in FILE_LINK_RE.finditer(text):
            file_ids.add(int(match.group(2)))
    return file_ids


def collect_embedded_missing(course_dir: Path):
    course = load_json(course_dir / "_metadata" / "course.json", {})
    course_id = course.get("id")
    if not course_id:
        return []
    api_items = load_json(course_dir / "_metadata" / "files.json", [])
    api_ids = {item.get("id") for item in api_items if isinstance(item, dict) and item.get("id") is not None}
    embedded_ids = sorted(file_id for file_id in collect_embedded_file_ids(course_dir) if file_id not in api_ids)
    if not embedded_ids:
        return []
    existing = load_json(course_dir / "_metadata" / "embedded_files.json", [])
    existing_by_id = {item.get("id"): item for item in existing if isinstance(item, dict) and item.get("id") is not None}
    pending = []
    for file_id in embedded_ids:
        cached = existing_by_id.get(file_id)
        if not cached:
            pending.append({"kind": "embedded_lookup", "course_id": course_id, "file_id": file_id})
            continue
        name = cached.get("display_name") or cached.get("filename") or f"file_{file_id}"
        target = course_dir / "Files" / "_embedded_from_pages" / ce.sanitize_name(name)
        size = cached.get("size")
        if target.exists() and size and target.stat().st_size == size:
            continue
        pending.append(
            {
                "kind": "embedded_file",
                "course_id": course_id,
                "file_id": file_id,
                "name": name,
                "size": size,
                "target": target,
                "cached": cached,
            }
        )
    return pending


def resolve_embedded_metadata(cdp: ce.CDPClient, course_dir: Path, lookups):
    if not lookups:
        return []
    course = load_json(course_dir / "_metadata" / "course.json", {})
    course_id = course.get("id")
    if not course_id:
        return []
    embedded_path = course_dir / "_metadata" / "embedded_files.json"
    existing = load_json(embedded_path, [])
    existing_by_id = {item.get("id"): item for item in existing if isinstance(item, dict) and item.get("id") is not None}
    resolved = []
    for item in lookups:
        file_id = item["file_id"]
        try:
            detail = ce.request_json_or_list(cdp, f"{ce.CANVAS_BASE}/api/v1/courses/{course_id}/files/{file_id}")
        except Exception as exc:
            ce.log(f"Embedded file metadata unavailable for {course_dir.name} / {file_id}: {exc}")
            continue
        existing_by_id[file_id] = detail
        resolved.append(detail)
    ce.save_json(embedded_path, list(sorted(existing_by_id.values(), key=lambda item: item.get("id", 0))))
    return resolved


def build_embedded_downloads(course_dir: Path):
    embedded = load_json(course_dir / "_metadata" / "embedded_files.json", [])
    downloads = []
    for item in embedded:
        if not isinstance(item, dict):
            continue
        name = item.get("display_name") or item.get("filename") or f"file_{item.get('id')}"
        target = course_dir / "Files" / "_embedded_from_pages" / ce.sanitize_name(name)
        size = item.get("size")
        if target.exists() and size and target.stat().st_size == size:
            continue
        if not item.get("url"):
            continue
        downloads.append(
            {
                "kind": "embedded_file",
                "course_id": item.get("course_id"),
                "file_id": item.get("id"),
                "name": name,
                "size": size,
                "url": item.get("url"),
                "target": target,
            }
        )
    return downloads


def download_with_retries(url: str, target: Path, size: int | None, retries: int = 3):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            ce.download_file_via_browser(url, target, size)
            if size and target.exists() and target.stat().st_size != size:
                raise RuntimeError(f"size mismatch after download: expected {size}, got {target.stat().st_size}")
            return
        except Exception as exc:
            last_error = exc
            ce.log(f"Retry {attempt}/{retries} failed for {target.name}: {exc}")
            time.sleep(min(5 * attempt, 15))
    raise last_error


def course_dirs():
    return [path for path in sorted(ce.ROOT_DIR.iterdir()) if path.is_dir() and path.name != "_metadata"]


def main():
    ce.start_edge_if_needed()
    page = ce.CDPClient(ce.get_or_create_canvas_target()["webSocketDebuggerUrl"])
    try:
        ce.wait_for_canvas_login(page)
        total_standard_missing = 0
        total_embedded_candidates = 0
        total_downloaded = 0
        for course_dir in course_dirs():
            standard_missing = collect_standard_missing(course_dir)
            embedded_pending = collect_embedded_missing(course_dir)
            lookup_items = [item for item in embedded_pending if item["kind"] == "embedded_lookup"]
            if lookup_items:
                resolve_embedded_metadata(page, course_dir, lookup_items)
            embedded_downloads = build_embedded_downloads(course_dir)

            ce.log(
                f"{course_dir.name}: standard_missing={len(standard_missing)} "
                f"embedded_candidates={len(embedded_downloads)}"
            )
            total_standard_missing += len(standard_missing)
            total_embedded_candidates += len(embedded_downloads)

            for item in standard_missing + embedded_downloads:
                try:
                    download_with_retries(item["url"], item["target"], item.get("size"))
                    total_downloaded += 1
                    ce.log(f"Downloaded: {course_dir.name} / {item['name']}")
                except Exception as exc:
                    ce.log(f"Still missing: {course_dir.name} / {item['name']} ({exc})")

        ce.log(
            "Deep supplement finished. "
            f"Downloaded {total_downloaded} items. "
            f"Standard missing before run: {total_standard_missing}. "
            f"Embedded candidates before run: {total_embedded_candidates}."
        )
    finally:
        page.close()


if __name__ == "__main__":
    main()
