#!/usr/bin/env python3
"""Capture Pixelscan fingerprint result screenshots from the ten Neko CloakBrowser instances."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PIXELSCAN_URL = "https://pixelscan.net/fingerprint-check"
DEFAULT_OUTPUT_DIR = "/home/yun/.hermes/browser_screenshots/neko-fingerprint"
DEFAULT_INSTANCES = 10
DEFAULT_CDP_URL = "http://127.0.0.1:9223"
DEFAULT_SESSION = "default"


def run(cmd: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode != 0:
        joined = " ".join(cmd)
        raise RuntimeError(
            f"command failed ({result.returncode}): {joined}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def docker_exec(container: str, args: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", container, *args], timeout=timeout, check=check)


def browser_use(container: str, args: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return docker_exec(
        container,
        [
            "browser-use",
            "--cdp-url",
            DEFAULT_CDP_URL,
            "--session",
            DEFAULT_SESSION,
            *args,
        ],
        timeout=timeout,
        check=check,
    )


def ensure_container(label: str) -> None:
    container = f"neko-cloakbrowser-{label}"
    inspect = run(
        ["docker", "inspect", "--format", "{{.State.Health.Status}} {{.State.Running}}", container],
        timeout=15,
        check=False,
    )
    if inspect.returncode != 0:
        raise RuntimeError(f"{container}: container not found")
    status = inspect.stdout.strip()
    if "true" not in status or "healthy" not in status:
        raise RuntimeError(f"{container}: expected healthy running container, got {status!r}")


def wait_for_result(container: str, label: str, timeout_s: int) -> None:
    deadline = time.monotonic() + timeout_s
    expected = [
        "your browser fingerprint is inconsistent",
        "your browser fingerprint is consistent",
        "masking detected",
        "no automated behavior",
        "no proxy detected",
        "proxy detected",
        "restart",
    ]
    last_state = ""
    while time.monotonic() < deadline:
        state = browser_use(container, ["state"], timeout=40, check=False)
        last_state = (state.stdout or "") + "\n" + (state.stderr or "")
        folded = last_state.lower()
        if any(token in folded for token in expected):
            return
        time.sleep(3)
    raise RuntimeError(f"neko-{label}: Pixelscan result did not appear within {timeout_s}s\n{last_state[-1200:]}")


def capture_one(label: str, output_dir: Path, wait_s: int) -> tuple[str, Path]:
    container = f"neko-cloakbrowser-{label}"
    ensure_container(label)
    remote_path = f"/tmp/neko-pixelscan-{label}.png"
    cache_bust = f"neko-{label}-{int(time.time())}"
    local_path = output_dir / f"neko-{label}-pixelscan.png"

    try:
        browser_use(container, ["open", f"{PIXELSCAN_URL}?neko={cache_bust}"], timeout=90)
        time.sleep(5)
        wait_for_result(container, label, wait_s)
        browser_use(container, ["screenshot", remote_path], timeout=90)
        run(["docker", "cp", f"{container}:{remote_path}", str(local_path)], timeout=60)
        if not local_path.exists() or local_path.stat().st_size < 10_000:
            raise RuntimeError(f"neko-{label}: screenshot missing or too small: {local_path}")
        return label, local_path
    finally:
        # Pixelscan can keep GPU/render workers busy after the visible result is
        # collected. Always leave the canary on a cheap real page so capture runs
        # do not leave the host with runaway CPU/GPU load. Avoid about:blank here:
        # this browser-use/CloakBrowser pairing normalizes it to https://about:blank.
        browser_use(container, ["open", "https://example.com"], timeout=30, check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", type=int, default=DEFAULT_INSTANCES, help="number of neko-cloakbrowser-XX containers to capture")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="base directory for screenshot runs")
    parser.add_argument("--wait-seconds", type=int, default=75, help="max seconds to wait for each Pixelscan result")
    parser.add_argument("--workers", type=int, default=5, help="parallel browser workers")
    parser.add_argument("--no-archive", action="store_true", help="do not create a tar.gz archive")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.instances < 1 or args.instances > 99:
        raise SystemExit("--instances must be between 1 and 99")
    labels = [f"{i:02d}" for i in range(1, args.instances + 1)]
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"output_dir={output_dir}")
    failures: list[str] = []
    captures: list[tuple[str, Path]] = []
    max_workers = max(1, min(args.workers, args.instances))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(capture_one, label, output_dir, args.wait_seconds): label
            for label in labels
        }
        for future in concurrent.futures.as_completed(future_map):
            label = future_map[future]
            try:
                captured = future.result()
                captures.append(captured)
                print(f"neko-{label}: saved {captured[1]}")
            except Exception as exc:  # noqa: BLE001 - CLI should aggregate all instance failures.
                failures.append(f"neko-{label}: {exc}")
                print(f"neko-{label}: FAILED {exc}", file=sys.stderr)

    captures.sort(key=lambda item: item[0])
    manifest = output_dir / "manifest.txt"
    manifest.write_text(
        "\n".join(f"neko-{label} {path.name} {path.stat().st_size}" for label, path in captures) + "\n",
        encoding="utf-8",
    )

    archive_path = None
    if not args.no_archive and captures:
        archive_path = shutil.make_archive(str(output_dir), "gztar", root_dir=output_dir)
        print(f"archive={archive_path}")

    if failures:
        (output_dir / "failures.txt").write_text("\n".join(failures) + "\n", encoding="utf-8")
        print("\n".join(failures), file=sys.stderr)
        return 1
    if len(captures) != args.instances:
        print(f"expected {args.instances} screenshots, got {len(captures)}", file=sys.stderr)
        return 1
    print(f"captured={len(captures)}/{args.instances}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
