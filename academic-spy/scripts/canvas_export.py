import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from html import unescape
from pathlib import Path

import websocket


EDGE_EXE = Path(os.environ.get("CANVAS_EDGE_EXE", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"))
EDGE_DEBUG_PORT = int(os.environ.get("CANVAS_EDGE_DEBUG_PORT", "9222"))
EDGE_PROFILE_DIR = os.environ.get("CANVAS_EDGE_PROFILE_DIR", "Default")
CANVAS_BASE = os.environ.get("CANVAS_BASE", "").rstrip("/")
COURSES_URL = os.environ.get("CANVAS_COURSES_URL", f"{CANVAS_BASE}/courses" if CANVAS_BASE else "about:blank")
ROOT_DIR = Path(os.environ.get("CANVAS_ROOT_DIR", str(Path.home() / "Downloads" / "canvas-export")))
DOWNLOAD_TMP_DIR = ROOT_DIR / "_downloads_tmp"


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def sanitize_name(name: str, default: str = "untitled") -> str:
    name = unescape((name or "").strip())
    name = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or default


def slugify(name: str) -> str:
    value = sanitize_name(name, default="item")
    return value[:180]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_unique_file(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def save_json(path: Path, payload) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_urls(text: str):
    if not text:
        return []
    urls = re.findall(r'https?://[^\s"\'<>]+', text)
    seen = []
    added = set()
    for url in urls:
        if url not in added:
            seen.append(url)
            added.add(url)
    return seen


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_url(url: str, params=None) -> str:
    if not params:
        return url
    query = urllib.parse.urlencode(params, doseq=True)
    separator = "&" if urllib.parse.urlparse(url).query else "?"
    return f"{url}{separator}{query}"


def parse_link_header(link_header: str):
    links = {}
    if not link_header:
        return links
    for part in link_header.split(","):
        section = part.strip()
        if ";" not in section:
            continue
        url_part, *rest = section.split(";")
        url_part = url_part.strip()
        if not (url_part.startswith("<") and url_part.endswith(">")):
            continue
        url = url_part[1:-1]
        params = {}
        for item in rest:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            params[key.strip()] = value.strip().strip('"')
        rel = params.get("rel")
        if rel:
            links[rel] = url
    return links


def infer_canvas_base(url: str):
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    if "instructure.com" in host or "canvas" in host:
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


def update_canvas_base(url: str):
    global CANVAS_BASE, COURSES_URL
    inferred = infer_canvas_base(url)
    if inferred and inferred != CANVAS_BASE:
        CANVAS_BASE = inferred
        if "CANVAS_COURSES_URL" not in os.environ:
            COURSES_URL = f"{CANVAS_BASE}/courses"
    return inferred


def is_canvas_target_url(url: str):
    inferred = infer_canvas_base(url)
    if not inferred:
        return False
    if CANVAS_BASE:
        return url.startswith(CANVAS_BASE)
    return True


def start_edge_if_needed() -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/version", timeout=2)
        return
    except Exception:
        pass

    log("Launching Edge with remote debugging enabled.")
    subprocess.Popen(
        [
            str(EDGE_EXE),
            f"--remote-debugging-port={EDGE_DEBUG_PORT}",
            f"--profile-directory={EDGE_PROFILE_DIR}",
            COURSES_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/version", timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Edge remote debugging endpoint did not come up.")


def get_targets():
    raw = urllib.request.urlopen(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/list", timeout=10).read()
    return json.loads(raw.decode("utf-8"))


def get_browser_ws_url():
    raw = urllib.request.urlopen(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/version", timeout=10).read()
    return json.loads(raw.decode("utf-8"))["webSocketDebuggerUrl"]


def get_or_create_canvas_target():
    targets = get_targets()
    for target in targets:
        if target.get("type") == "page" and is_canvas_target_url(target.get("url", "")):
            update_canvas_base(target.get("url", ""))
            return target
    encoded = urllib.parse.quote(COURSES_URL, safe="")
    request = urllib.request.Request(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/new?{encoded}", method="PUT")
    with urllib.request.urlopen(request, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_aux_target(url: str = "about:blank"):
    encoded = urllib.parse.quote(url, safe="")
    request = urllib.request.Request(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/new?{encoded}", method="PUT")
    with urllib.request.urlopen(request, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def close_target(target_id: str):
    for method in ["PUT", "GET"]:
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{EDGE_DEBUG_PORT}/json/close/{target_id}", method=method)
            urllib.request.urlopen(request, timeout=10).read()
            return
        except Exception:
            continue


class CDPClient:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
        self.next_id = 0
        self.events = []

    def call(self, method: str, params=None):
        self.next_id += 1
        msg_id = self.next_id
        payload = {"id": msg_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(payload))
        while True:
            message = json.loads(self.ws.recv())
            if "id" not in message:
                self.events.append(message)
                continue
            if message.get("id") != msg_id:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP {method} failed: {message['error']}")
            return message.get("result", {})

    def clear_events(self):
        self.events.clear()

    def wait_for_event(self, predicate, timeout: float = 30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for index, event in enumerate(self.events):
                if predicate(event):
                    return self.events.pop(index)
            self.ws.settimeout(max(0.1, deadline - time.time()))
            try:
                message = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if "id" in message:
                continue
            if predicate(message):
                return message
            self.events.append(message)
        raise TimeoutError("Timed out waiting for CDP event.")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def evaluate(cdp: CDPClient, expression: str):
    result = cdp.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        },
    )
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"].get("text") or "Runtime.evaluate failed")
    return result.get("result", {}).get("value")


def wait_for_canvas_login(cdp: CDPClient):
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")
    cdp.call("Network.enable")

    login_notified = False
    deadline = time.time() + 60 * 30
    while time.time() < deadline:
        location = evaluate(cdp, "location.href")
        title = evaluate(cdp, "document.title")
        update_canvas_base(location)
        if CANVAS_BASE and location.startswith(CANVAS_BASE):
            log(f"Canvas session detected: {title}")
            return
        if not login_notified:
            log("Waiting for you to finish Canvas login in the opened Edge window.")
            login_notified = True
        time.sleep(3)
    raise TimeoutError("Timed out waiting for Canvas login.")


def browser_fetch(cdp: CDPClient, url: str):
    payload = evaluate(
        cdp,
        f"""
        (async () => {{
          const response = await fetch({js(url)}, {{ credentials: 'include' }});
          const body = await response.text();
          return {{
            ok: response.ok,
            status: response.status,
            url: response.url,
            headers: Array.from(response.headers.entries()),
            body
          }};
        }})()
        """,
    )
    if not payload["ok"]:
        raise RuntimeError(f"Fetch failed for {url}: HTTP {payload['status']}")
    payload["headers"] = {key.lower(): value for key, value in payload.get("headers", [])}
    return payload


def paginate(cdp: CDPClient, url: str, params=None):
    items = []
    next_url = build_url(url, params)
    while next_url:
        response = browser_fetch(cdp, next_url)
        payload = json.loads(response["body"])
        if isinstance(payload, list):
            items.extend(payload)
        else:
            return payload
        next_url = parse_link_header(response["headers"].get("link", "")).get("next")
    return items


def request_json_or_list(cdp: CDPClient, url: str, params=None):
    response = browser_fetch(cdp, build_url(url, params))
    return json.loads(response["body"])


def safe_rel_folder(full_name: str) -> Path:
    if not full_name:
        return Path()
    parts = [sanitize_name(part) for part in full_name.split("/") if part.strip()]
    if parts and parts[0].lower() == "course files":
        parts = parts[1:]
    return Path(*parts) if parts else Path()


def download_file_via_browser(url: str, destination: Path, expected_size: int | None = None):
    ensure_dir(destination.parent)
    timeout = max(180, int((expected_size or 0) / (1024 * 1024)) * 15 + 60)
    target = create_aux_target("about:blank")
    file_cdp = CDPClient(target["webSocketDebuggerUrl"])
    try:
        file_cdp.clear_events()
        file_cdp.call("Page.enable")
        file_cdp.call("Network.enable")
        file_cdp.call("Page.navigate", {"url": url})

        request_id = None
        response_url = None
        while True:
            event = file_cdp.wait_for_event(
                lambda e: e.get("method")
                in {
                    "Network.responseReceived",
                    "Network.loadingFinished",
                    "Network.loadingFailed",
                },
                timeout=timeout,
            )
            method = event.get("method")
            params = event.get("params", {})
            if method == "Network.responseReceived":
                response = params.get("response", {})
                candidate_url = response.get("url", "")
                if candidate_url.startswith("http"):
                    request_id = params.get("requestId")
                    response_url = candidate_url
            elif method == "Network.loadingFailed" and params.get("requestId") == request_id:
                error = params.get("errorText")
                if response_url and (
                    "cdn.inst-fs" in response_url
                    or "canvas-user-content.com" in response_url
                    or "cloudfront.net" in response_url
                ):
                    download_direct(response_url, destination)
                    return
                raise RuntimeError(f"Network loading failed for {response_url or url}: {error}")
            elif method == "Network.loadingFinished" and params.get("requestId") == request_id:
                if not response_url:
                    raise RuntimeError(f"Did not resolve final download URL for {url}")
                download_direct(response_url, destination)
                return
    finally:
        file_cdp.close()
        close_target(target["id"])


def download_direct(url: str, destination: Path):
    ensure_dir(destination.parent)
    ensure_dir(DOWNLOAD_TMP_DIR)
    temp_path = DOWNLOAD_TMP_DIR / f"{uuid.uuid4().hex}.part"
    curl_cmd = [
        "curl.exe",
        "--fail",
        "--location",
        "--retry",
        "3",
        "--retry-delay",
        "2",
        "--output",
        str(temp_path),
        url,
    ]
    try:
        result = subprocess.run(curl_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=1800)
        if result.returncode == 0 and temp_path.exists() and temp_path.stat().st_size > 0:
            os.replace(temp_path, destination)
            return

        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=300) as response, open(temp_path, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        if temp_path.exists() and temp_path.stat().st_size > 0:
            os.replace(temp_path, destination)
            return
        raise RuntimeError(f"Downloaded empty file from {url}")
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass


def save_html_bundle(base_path: Path, title: str, html: str, metadata: dict):
    save_text(base_path.with_suffix(".html"), html or "")
    save_text(base_path.with_suffix(".txt"), html_to_text(html or ""))
    save_json(base_path.with_suffix(".json"), metadata)


def export_course(cdp: CDPClient, course: dict, manifest: dict):
    course_id = course["id"]
    course_name = course.get("name") or course.get("course_code") or f"course_{course_id}"
    course_dir = ensure_dir(ROOT_DIR / slugify(course_name))
    log(f"Exporting {course_name}")

    course_summary = {
        "id": course_id,
        "name": course_name,
        "root": str(course_dir),
        "downloaded_files": 0,
        "pages": 0,
        "assignments": 0,
        "announcements": 0,
        "discussions": 0,
        "external_links": 0,
    }
    manifest["courses"].append(course_summary)

    metadata_dir = ensure_dir(course_dir / "_metadata")
    files_dir = ensure_dir(course_dir / "Files")
    pages_dir = ensure_dir(course_dir / "Pages")
    assignments_dir = ensure_dir(course_dir / "Assignments")
    announcements_dir = ensure_dir(course_dir / "Announcements")
    discussions_dir = ensure_dir(course_dir / "Discussions")

    save_json(metadata_dir / "course.json", course)

    syllabus_html = course.get("syllabus_body") or ""
    if syllabus_html:
        save_html_bundle(metadata_dir / "syllabus", "syllabus", syllabus_html, {"course_id": course_id})

    try:
        folders = paginate(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/folders", {"per_page": 100})
    except Exception as exc:
        log(f"Folder listing unavailable for {course_name}: {exc}")
        folders = []
    save_json(metadata_dir / "folders.json", folders)
    folder_by_id = {folder["id"]: folder for folder in folders}

    try:
        files = paginate(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/files", {"per_page": 100})
    except Exception as exc:
        log(f"File listing unavailable for {course_name}: {exc}")
        files = []
    save_json(metadata_dir / "files.json", files)
    for file_info in files:
        filename = sanitize_name(file_info.get("display_name") or file_info.get("filename") or f"file_{file_info['id']}")
        folder = folder_by_id.get(file_info.get("folder_id"))
        rel_folder = safe_rel_folder(folder.get("full_name") if folder else "")
        target = files_dir / rel_folder / filename
        if target.exists() and file_info.get("size") and target.stat().st_size == file_info.get("size"):
            course_summary["downloaded_files"] += 1
            continue
        try:
            download_file_via_browser(file_info["url"], target, file_info.get("size"))
            course_summary["downloaded_files"] += 1
        except Exception as exc:
            log(f"File download failed for {course_name}: {filename} ({exc})")

    try:
        pages = paginate(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/pages", {"per_page": 100})
    except Exception as exc:
        log(f"Page listing unavailable for {course_name}: {exc}")
        pages = []
    save_json(metadata_dir / "pages_index.json", pages)
    page_details = []
    for page in pages:
        page_url = page.get("url")
        if not page_url:
            continue
        try:
            detail = request_json_or_list(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/pages/{urllib.parse.quote(page_url, safe='')}")
        except Exception as exc:
            log(f"Page fetch failed for {course_name}: {page_url} ({exc})")
            continue
        page_details.append(detail)
        base = pages_dir / slugify(detail.get("title") or page_url)
        save_html_bundle(base, detail.get("title") or page_url, detail.get("body") or "", detail)
        course_summary["pages"] += 1

    try:
        assignments = paginate(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/assignments", {"per_page": 100})
    except Exception as exc:
        log(f"Assignment listing unavailable for {course_name}: {exc}")
        assignments = []
    save_json(metadata_dir / "assignments.json", assignments)
    for assignment in assignments:
        base = assignments_dir / slugify(assignment.get("name") or f"assignment_{assignment['id']}")
        save_html_bundle(base, assignment.get("name") or "", assignment.get("description") or "", assignment)
        course_summary["assignments"] += 1

    try:
        modules = paginate(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/modules", {"include[]": "items", "per_page": 100})
    except Exception as exc:
        log(f"Module listing unavailable for {course_name}: {exc}")
        modules = []
    save_json(metadata_dir / "modules.json", modules)

    try:
        quizzes = paginate(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/quizzes", {"per_page": 100})
    except Exception:
        quizzes = []
    save_json(metadata_dir / "quizzes.json", quizzes)

    try:
        announcements = paginate(
            cdp,
            f"{CANVAS_BASE}/api/v1/announcements",
            {"context_codes[]": f"course_{course_id}", "per_page": 100},
        )
    except Exception:
        announcements = []
    save_json(metadata_dir / "announcements.json", announcements)
    for item in announcements:
        base = announcements_dir / slugify(item.get("title") or f"announcement_{item.get('id', 'x')}")
        save_html_bundle(base, item.get("title") or "", item.get("message") or "", item)
        course_summary["announcements"] += 1

    try:
        discussions = paginate(cdp, f"{CANVAS_BASE}/api/v1/courses/{course_id}/discussion_topics", {"per_page": 100})
    except Exception:
        discussions = []
    save_json(metadata_dir / "discussions.json", discussions)
    for item in discussions:
        base = discussions_dir / slugify(item.get("title") or f"discussion_{item.get('id', 'x')}")
        save_html_bundle(base, item.get("title") or "", item.get("message") or "", item)
        course_summary["discussions"] += 1

    external_links = []
    seen_links = set()
    blobs = [syllabus_html]
    blobs.extend(page.get("body") or "" for page in page_details if isinstance(page, dict))
    blobs.extend(item.get("body") or "" for item in announcements if isinstance(item, dict))
    blobs.extend(item.get("message") or "" for item in discussions if isinstance(item, dict))
    blobs.extend(item.get("description") or "" for item in assignments if isinstance(item, dict))
    for module in modules:
        for item in module.get("items", []):
            for value in [item.get("html_url"), item.get("external_url"), item.get("url")]:
                if value and value not in seen_links:
                    seen_links.add(value)
                    external_links.append(value)
    for blob in blobs:
        for url in extract_urls(blob):
            if url not in seen_links:
                seen_links.add(url)
                external_links.append(url)
    external_links = sorted(external_links)
    save_text(course_dir / "external_links.txt", "\n".join(external_links) + ("\n" if external_links else ""))
    course_summary["external_links"] = len(external_links)


def get_courses(cdp: CDPClient):
    courses = paginate(
        cdp,
        f"{CANVAS_BASE}/api/v1/courses",
        {"include[]": ["term", "syllabus_body"], "per_page": 100},
    )
    filtered = []
    seen = set()
    for course in courses:
        if not isinstance(course, dict):
            continue
        course_id = course.get("id")
        if not course_id or course_id in seen:
            continue
        seen.add(course_id)
        filtered.append(course)
    return filtered


def main():
    ensure_dir(ROOT_DIR)
    ensure_dir(DOWNLOAD_TMP_DIR)
    for path in DOWNLOAD_TMP_DIR.iterdir():
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                pass
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root_dir": str(ROOT_DIR),
        "canvas_base": CANVAS_BASE,
        "courses": [],
    }

    start_edge_if_needed()
    bootstrap_cdp = CDPClient(get_or_create_canvas_target()["webSocketDebuggerUrl"])
    try:
        wait_for_canvas_login(bootstrap_cdp)
        me = request_json_or_list(bootstrap_cdp, f"{CANVAS_BASE}/api/v1/users/self")
        save_json(ROOT_DIR / "_metadata" / "user.json", me)

        courses = get_courses(bootstrap_cdp)
        save_json(ROOT_DIR / "_metadata" / "courses.json", courses)
        log(f"Found {len(courses)} courses to export.")
    finally:
        bootstrap_cdp.close()

    for course in courses:
        cdp = CDPClient(get_or_create_canvas_target()["webSocketDebuggerUrl"])
        try:
            export_course(cdp, course, manifest)
            save_json(ROOT_DIR / "_metadata" / "manifest.partial.json", manifest)
        except Exception as exc:
            log(f"Course export failed for {course.get('name')}: {exc}")
        finally:
            cdp.close()

    save_json(ROOT_DIR / "_metadata" / "manifest.json", manifest)
    log("Canvas export finished.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Export interrupted.")
        sys.exit(1)
    except Exception as exc:
        log(f"Export failed: {exc}")
        sys.exit(1)
