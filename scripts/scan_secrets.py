"""Basic credential-pattern guard. Prints paths only, never matched values.

Default: scan current tracked file contents. --history scans reachable commits.
This is not an exhaustive secret detector; use provider-side revocation and review.
"""
import argparse
from pathlib import Path
import re
import subprocess

PATTERNS = [
    re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    re.compile(rb"sk-(?:proj-)?[0-9A-Za-z_-]{20,}"),
    re.compile(rb"gh[pousr]_[0-9A-Za-z]{30,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    failures = set()
    if args.history:
        objects = git("rev-list", "--objects", "--all").decode().splitlines()
        for entry in objects:
            sha, _, name = entry.partition(" ")
            if git("cat-file", "-t", sha).strip() != b"blob":
                continue
            data = git("cat-file", "blob", sha)
            if any(pattern.search(data) for pattern in PATTERNS):
                failures.add(name or "unnamed historical blob")
    else:
        for raw in git("ls-files", "-z").split(b"\0"):
            if not raw:
                continue
            path = Path(raw.decode())
            if path.is_file() and any(pattern.search(path.read_bytes()) for pattern in PATTERNS):
                failures.add(str(path))
    if failures:
        print("Credential-like content detected in:")
        for name in sorted(failures):
            print(" -", name)
        return 1
    print("No supported credential patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
