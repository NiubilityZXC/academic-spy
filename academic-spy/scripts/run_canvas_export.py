import sys

from canvas_runtime import apply_runtime


ce = apply_runtime()


if __name__ == "__main__":
    try:
        ce.main()
    except KeyboardInterrupt:
        ce.log("Export interrupted.")
        sys.exit(1)
    except Exception as exc:
        ce.log(f"Export failed: {exc}")
        sys.exit(1)
