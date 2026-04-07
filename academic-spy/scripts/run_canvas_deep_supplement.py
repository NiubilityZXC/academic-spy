import sys

import canvas_deep_supplement as cds
from canvas_runtime import apply_runtime, course_dirs, patch_deep_supplement


ce = apply_runtime()
patch_deep_supplement(cds)


def main(selected_names=None):
    ce.start_edge_if_needed()
    page = ce.CDPClient(ce.get_or_create_canvas_target()["webSocketDebuggerUrl"])
    try:
        ce.wait_for_canvas_login(page)
        total_standard_missing = 0
        total_embedded_candidates = 0
        total_downloaded = 0
        for course_dir in course_dirs(ce.ROOT_DIR, selected_names):
            standard_missing = cds.collect_standard_missing(course_dir)
            embedded_pending = cds.collect_embedded_missing(course_dir)
            lookup_items = [item for item in embedded_pending if item["kind"] == "embedded_lookup"]
            if lookup_items:
                cds.resolve_embedded_metadata(page, course_dir, lookup_items)
            embedded_downloads = cds.build_embedded_downloads(course_dir)

            ce.log(
                f"{course_dir.name}: standard_missing={len(standard_missing)} "
                f"embedded_candidates={len(embedded_downloads)}"
            )
            total_standard_missing += len(standard_missing)
            total_embedded_candidates += len(embedded_downloads)

            for item in standard_missing + embedded_downloads:
                try:
                    cds.download_with_retries(item["url"], item["target"], item.get("size"))
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
    main(sys.argv[1:] or None)
