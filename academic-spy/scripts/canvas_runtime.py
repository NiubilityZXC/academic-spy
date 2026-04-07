import os
import re
from pathlib import Path

import canvas_export as ce


DEFAULT_EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DEFAULT_EDGE_DEBUG_PORT = 9222
DEFAULT_EDGE_PROFILE_DIR = "Default"
DEFAULT_CANVAS_BASE = ""
DEFAULT_ROOT_DIR = Path.home() / "Downloads" / "canvas-export"


def apply_runtime():
    ce.EDGE_EXE = Path(os.environ.get("CANVAS_EDGE_EXE", DEFAULT_EDGE_EXE))
    ce.EDGE_DEBUG_PORT = int(os.environ.get("CANVAS_EDGE_DEBUG_PORT", str(DEFAULT_EDGE_DEBUG_PORT)))
    ce.EDGE_PROFILE_DIR = os.environ.get("CANVAS_EDGE_PROFILE_DIR", DEFAULT_EDGE_PROFILE_DIR)
    ce.CANVAS_BASE = os.environ.get("CANVAS_BASE", DEFAULT_CANVAS_BASE).rstrip("/")
    ce.COURSES_URL = os.environ.get("CANVAS_COURSES_URL", f"{ce.CANVAS_BASE}/courses")
    ce.ROOT_DIR = Path(os.environ.get("CANVAS_ROOT_DIR", str(DEFAULT_ROOT_DIR)))
    ce.DOWNLOAD_TMP_DIR = ce.ROOT_DIR / "_downloads_tmp"
    return ce


def course_dirs(root: Path, selected_names=None):
    paths = [path for path in sorted(root.iterdir()) if path.is_dir() and not path.name.startswith("_")]
    if not selected_names:
        return paths
    by_name = {path.name: path for path in paths}
    return [by_name[name] for name in selected_names if name in by_name]


def patch_deep_supplement(module):
    module.FILE_LINK_RE = re.compile(
        r"(?:https?://[^/]+)?(?:/api/v1)?/courses/(\d+)/files/(\d+)",
        re.I,
    )
    return module
