import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run(script_name, *args):
    command = [sys.executable, str(SCRIPT_DIR / script_name), *args]
    print(">", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the Canvas export, supplement, and verification workflow."
    )
    parser.add_argument("--skip-export", action="store_true", help="Skip the full export phase.")
    parser.add_argument("--skip-deep", action="store_true", help="Skip the deep supplement phase.")
    parser.add_argument("--skip-embedded", action="store_true", help="Skip the embedded supplement phase.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip the verification phase.")
    parser.add_argument(
        "--course",
        action="append",
        default=[],
        help="Limit supplement phases to one course name. Repeat for multiple courses.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.skip_export:
        run("run_canvas_export.py")
    if not args.skip_deep:
        run("run_canvas_deep_supplement.py", *args.course)
    if not args.skip_embedded:
        run("run_canvas_embedded_supplement.py", *args.course)
    if not args.skip_verify:
        run("canvas_verify.py")


if __name__ == "__main__":
    main()
