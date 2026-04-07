import json
import re

from canvas_runtime import apply_runtime, course_dirs


ce = apply_runtime()


TEXT_SUFFIXES = {".html", ".txt", ".json"}


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def build_folder_map(course_dir):
    folders = load_json(course_dir / "_metadata" / "folders.json", [])
    return {
        int(folder["id"]): folder
        for folder in folders
        if isinstance(folder, dict) and folder.get("id") is not None
    }


def expected_standard_path(course_dir, file_item, folder_map):
    name = file_item.get("display_name") or file_item.get("filename") or f"file_{file_item.get('id')}"
    folder = folder_map.get(file_item.get("folder_id"))
    rel_folder = ce.safe_rel_folder(folder.get("full_name") if folder else "")
    return course_dir / "Files" / rel_folder / ce.sanitize_name(name)


def verify_standard_files(course_dir):
    files = load_json(course_dir / "_metadata" / "files.json", [])
    folder_map = build_folder_map(course_dir)
    missing = []
    for item in files:
        if not isinstance(item, dict):
            continue
        target = expected_standard_path(course_dir, item, folder_map)
        expected_size = item.get("size")
        if not target.exists():
            missing.append(
                {
                    "file_id": item.get("id"),
                    "name": target.name,
                    "reason": "missing",
                    "expected_path": str(target),
                    "expected_size": expected_size,
                }
            )
            continue
        if isinstance(expected_size, int) and expected_size > 0:
            actual_size = target.stat().st_size
            if actual_size != expected_size:
                missing.append(
                    {
                        "file_id": item.get("id"),
                        "name": target.name,
                        "reason": "size_mismatch",
                        "expected_path": str(target),
                        "expected_size": expected_size,
                        "actual_size": actual_size,
                    }
                )
    return missing


def load_embedded_report(course_dir):
    raw = load_json(course_dir / "_metadata" / "embedded_download_report.json", {})
    if isinstance(raw, list):
        return {
            str(item["file_id"]): item
            for item in raw
            if isinstance(item, dict) and item.get("file_id") is not None
        }
    if isinstance(raw, dict):
        return raw
    return {}


def scan_referenced_ids(course_dir):
    standard_ids = {
        str(item["id"])
        for item in load_json(course_dir / "_metadata" / "files.json", [])
        if isinstance(item, dict) and item.get("id") is not None
    }
    report_ids = set(load_embedded_report(course_dir).keys())
    referenced = set()
    patterns = [
        re.compile(rf"{re.escape(ce.CANVAS_BASE)}(?:/api/v1)?/courses/\d+/files/(\d+)", re.I),
        re.compile(r"/courses/\d+/files/(\d+)", re.I),
        re.compile(r"/api/v1/courses/\d+/files/(\d+)", re.I),
    ]
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
        for pattern in patterns:
            for match in pattern.finditer(text or ""):
                referenced.add(match.group(1))
    return sorted(referenced - standard_ids - report_ids)


def verify_course(course_dir):
    report = load_embedded_report(course_dir)
    embedded_failed = [
        item
        for item in report.values()
        if isinstance(item, dict) and item.get("status") == "failed"
    ]
    embedded_downloaded = [
        item
        for item in report.values()
        if isinstance(item, dict) and item.get("status") == "downloaded"
    ]
    embedded_dir = course_dir / "Files" / "_embedded_from_pages"
    embedded_actual = 0
    if embedded_dir.exists():
        embedded_actual = sum(1 for path in embedded_dir.iterdir() if path.is_file())
    standard_missing = verify_standard_files(course_dir)
    unaccounted = scan_referenced_ids(course_dir)
    return {
        "course": course_dir.name,
        "standard_missing": standard_missing,
        "standard_missing_count": len(standard_missing),
        "embedded_downloaded_count": len(embedded_downloaded),
        "embedded_failed": embedded_failed,
        "embedded_failed_count": len(embedded_failed),
        "embedded_actual_count": embedded_actual,
        "unaccounted_referenced_ids": unaccounted,
    }


def main():
    root = ce.ROOT_DIR
    summary = {
        "canvas_base": ce.CANVAS_BASE,
        "root_dir": str(root),
        "courses": [],
        "totals": {
            "files": 0,
            "size_bytes": 0,
            "size_gb": 0,
            "standard_missing": 0,
            "embedded_failed": 0,
            "embedded_downloaded": 0,
            "embedded_actual": 0,
            "unaccounted_referenced_ids": 0,
        },
    }

    for path in root.rglob("*"):
        if path.is_file():
            summary["totals"]["files"] += 1
            summary["totals"]["size_bytes"] += path.stat().st_size

    for course_dir in course_dirs(root):
        course_summary = verify_course(course_dir)
        summary["courses"].append(course_summary)
        summary["totals"]["standard_missing"] += course_summary["standard_missing_count"]
        summary["totals"]["embedded_failed"] += course_summary["embedded_failed_count"]
        summary["totals"]["embedded_downloaded"] += course_summary["embedded_downloaded_count"]
        summary["totals"]["embedded_actual"] += course_summary["embedded_actual_count"]
        summary["totals"]["unaccounted_referenced_ids"] += len(course_summary["unaccounted_referenced_ids"])

    summary["totals"]["size_gb"] = round(summary["totals"]["size_bytes"] / (1024 ** 3), 3)
    ce.save_json(root / "_metadata" / "verification_report.json", summary)

    ce.log(
        "Verification finished. "
        f"files={summary['totals']['files']} "
        f"size_gb={summary['totals']['size_gb']} "
        f"standard_missing={summary['totals']['standard_missing']} "
        f"embedded_failed={summary['totals']['embedded_failed']} "
        f"embedded_actual={summary['totals']['embedded_actual']} "
        f"unaccounted_ids={summary['totals']['unaccounted_referenced_ids']}"
    )

    for course in summary["courses"]:
        if (
            course["standard_missing_count"]
            or course["embedded_failed_count"]
            or course["unaccounted_referenced_ids"]
        ):
            ce.log(
                f"{course['course']}: "
                f"standard_missing={course['standard_missing_count']} "
                f"embedded_failed={course['embedded_failed_count']} "
                f"unaccounted_ids={len(course['unaccounted_referenced_ids'])}"
            )


if __name__ == "__main__":
    main()
