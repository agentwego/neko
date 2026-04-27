#!/usr/bin/env python3
"""Batch-test and record IP purity for Neko CloakBrowser instances.

The live collection path uses the in-container ``browser-use`` command against
BrowserLeaks' IP page, stores raw state/screenshot evidence, writes structured
observations to a local SQLite database, and renders a Markdown/HTML/PDF report.

A ``--from-state`` mode is intentionally provided so an already captured
browser-use JSON state can be imported and reported without touching a live
browser session. This keeps verification cheap and reproducible.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import markdown  # type: ignore
except Exception:  # pragma: no cover - checked at runtime for report rendering.
    markdown = None

BROWSERLEAKS_IP_URL = "https://browserleaks.com/ip"
DEFAULT_OUTPUT_DIR = "/home/yun/.hermes/browser_screenshots/ip-purity/runs"
DEFAULT_DB_PATH = "/home/yun/.hermes/browser_screenshots/ip-purity/ip-purity.sqlite3"
DEFAULT_CDP_URL = "http://127.0.0.1:9223"
DEFAULT_SESSION = "default"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  source TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  instance TEXT NOT NULL,
  site TEXT NOT NULL,
  ip TEXT NOT NULL DEFAULT '',
  country TEXT NOT NULL DEFAULT '',
  region TEXT NOT NULL DEFAULT '',
  city TEXT NOT NULL DEFAULT '',
  isp TEXT NOT NULL DEFAULT '',
  organization TEXT NOT NULL DEFAULT '',
  network TEXT NOT NULL DEFAULT '',
  usage_type TEXT NOT NULL DEFAULT '',
  timezone TEXT NOT NULL DEFAULT '',
  passive_os TEXT NOT NULL DEFAULT '',
  link_type TEXT NOT NULL DEFAULT '',
  sec_ch_ua_platform TEXT NOT NULL DEFAULT '',
  user_agent TEXT NOT NULL DEFAULT '',
  proxy_flag TEXT NOT NULL DEFAULT 'unknown',
  purity_score INTEGER NOT NULL DEFAULT 0,
  purity_label TEXT NOT NULL DEFAULT 'unknown',
  notes TEXT NOT NULL DEFAULT '',
  screenshot_path TEXT NOT NULL DEFAULT '',
  state_path TEXT NOT NULL DEFAULT '',
  raw_text_path TEXT NOT NULL DEFAULT '',
  raw_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_observations_ip ON observations(ip);
CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(run_id);
"""

FIELD_ALIASES = {
    "IP Address": "ip",
    "Country": "country",
    "State/Region": "region",
    "City": "city",
    "ISP": "isp",
    "Organization": "organization",
    "Network": "network",
    "Usage Type": "usage_type",
    "Timezone": "timezone",
    "OS": "passive_os",
    "Link Type": "link_type",
    "Sec-CH-UA-Platform": "sec_ch_ua_platform",
    "User-Agent": "user_agent",
}

HOSTING_PATTERNS = re.compile(r"hosting|datacenter|data center|corporate|business|server|cloud|vpn|proxy", re.I)
RESIDENTIAL_PATTERNS = re.compile(r"isp|residential|consumer|fixed line|mobile|cellular", re.I)
TUNNEL_PATTERNS = re.compile(r"ipsec|gre|vpn|proxy|tunnel", re.I)


def run(cmd: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def docker_exec(container: str, args: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", container, *args], timeout=timeout, check=check)


def browser_use(container: str, args: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return docker_exec(
        container,
        ["browser-use", "--cdp-url", DEFAULT_CDP_URL, "--session", DEFAULT_SESSION, *args],
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


def extract_raw_text(state: dict[str, Any]) -> str:
    if isinstance(state.get("data"), dict):
        raw = state["data"].get("_raw_text")
        if isinstance(raw, str):
            return raw
    for key in ("_raw_text", "text", "raw_text"):
        raw = state.get(key)
        if isinstance(raw, str):
            return raw
    return json.dumps(state, ensure_ascii=False)


def clean_lines(raw_text: str) -> list[str]:
    cleaned: list[str] = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"\[\d+\].*", line):
            continue
        if line in {"<td />", "<tr />", "<table />"}:
            continue
        cleaned.append(line)
    return cleaned


def normalize_multiline_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_browserleaks_raw_text(raw_text: str) -> dict[str, str]:
    lines = clean_lines(raw_text)
    parsed: dict[str, str] = {}
    labels = set(FIELD_ALIASES)
    for idx, line in enumerate(lines):
        if line not in labels:
            continue
        key = FIELD_ALIASES[line]
        values: list[str] = []
        for follow in lines[idx + 1 : idx + 5]:
            if follow in labels:
                break
            if follow.startswith("http") and key != "user_agent":
                continue
            values.append(follow)
            if key not in {"network", "user_agent"}:
                break
        if values:
            parsed[key] = normalize_multiline_value(" ".join(values))
    return parsed


def score_observation(observation: dict[str, Any]) -> dict[str, Any]:
    score = 100
    notes: list[str] = []
    usage_type = str(observation.get("usage_type") or "")
    passive_os = str(observation.get("passive_os") or "")
    user_agent = str(observation.get("user_agent") or "")
    link_type = str(observation.get("link_type") or "")
    proxy_flag = "unknown"

    if HOSTING_PATTERNS.search(usage_type):
        score -= 55
        proxy_flag = "yes"
        notes.append("hosting/datacenter usage type")
    elif RESIDENTIAL_PATTERNS.search(usage_type):
        score -= 5
        proxy_flag = "no"
        notes.append("usage type looks residential/ISP-like")
    elif usage_type:
        score -= 20
        notes.append("usage type needs review")

    if passive_os and "linux" in user_agent.lower() and passive_os.lower() not in {"linux", "unknown"}:
        score -= 15
        notes.append("passive OS mismatch")

    if TUNNEL_PATTERNS.search(link_type):
        score -= 10
        notes.append("tunnel/VPN-like link type")

    if not observation.get("ip"):
        score -= 30
        notes.append("missing IP extraction")

    score = max(0, min(100, score))
    has_mismatch = any(note in notes for note in ("passive OS mismatch", "tunnel/VPN-like link type"))
    if score >= 80 and not has_mismatch:
        label = "clean"
    elif score >= 60:
        label = "usable"
    elif score >= 40:
        label = "risky"
    else:
        label = "poor"

    result = dict(observation)
    result.update({"proxy_flag": proxy_flag, "purity_score": score, "purity_label": label, "notes": "; ".join(notes)})
    return result


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


def create_run(db_path: Path, run_id: str, *, source: str, notes: str = "") -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO runs(run_id, created_at, source, notes) VALUES (?, ?, ?, ?)",
            (run_id, dt.datetime.now().isoformat(timespec="seconds"), source, notes),
        )


def insert_observation(db_path: Path, *, run_id: str, observation: dict[str, Any]) -> None:
    observed_at = str(observation.get("observed_at") or dt.datetime.now().isoformat(timespec="seconds"))
    raw_json = observation.get("raw_json")
    if not isinstance(raw_json, str):
        raw_json = json.dumps(raw_json or {}, ensure_ascii=False, sort_keys=True)
    columns = [
        "run_id", "observed_at", "instance", "site", "ip", "country", "region", "city", "isp", "organization",
        "network", "usage_type", "timezone", "passive_os", "link_type", "sec_ch_ua_platform", "user_agent",
        "proxy_flag", "purity_score", "purity_label", "notes", "screenshot_path", "state_path", "raw_text_path", "raw_json",
    ]
    values = {
        "run_id": run_id,
        "observed_at": observed_at,
        "site": "browserleaks-ip",
        "proxy_flag": "unknown",
        "purity_score": 0,
        "purity_label": "unknown",
        **observation,
        "raw_json": raw_json,
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"INSERT INTO observations({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            [values.get(column, "") for column in columns],
        )


def load_observations(db_path: Path, run_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM observations WHERE run_id = ? ORDER BY instance, observed_at",
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def wait_for_browserleaks(container: str, timeout_s: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last_payload = ""
    while time.monotonic() < deadline:
        state = browser_use(container, ["--json", "state"], timeout=45, check=False)
        payload = state.stdout or state.stderr or ""
        last_payload = payload
        try:
            data = json.loads(payload)
        except Exception:
            data = {"data": {"_raw_text": payload}}
        raw_text = extract_raw_text(data)
        if "IP Address" in raw_text and "Usage Type" in raw_text:
            return data
        time.sleep(3)
    raise RuntimeError(f"BrowserLeaks result did not appear within {timeout_s}s\n{last_payload[-1200:]}")


def collect_one(label: str, output_dir: Path, wait_s: int) -> dict[str, Any]:
    container = f"neko-cloakbrowser-{label}"
    ensure_container(label)
    instance_dir = output_dir / f"neko-{label}"
    instance_dir.mkdir(parents=True, exist_ok=True)
    remote_screenshot = f"/tmp/neko-{label}-browserleaks-ip.png"
    local_screenshot = instance_dir / "browserleaks-ip.png"
    state_path = instance_dir / "browserleaks-state.json"
    raw_text_path = instance_dir / "browserleaks-state.txt"
    cache_bust = f"neko-{label}-{int(time.time())}"
    try:
        browser_use(container, ["open", f"{BROWSERLEAKS_IP_URL}?neko={cache_bust}"], timeout=90)
        state = wait_for_browserleaks(container, wait_s)
        raw_text = extract_raw_text(state)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        raw_text_path.write_text(raw_text, encoding="utf-8")
        browser_use(container, ["screenshot", remote_screenshot], timeout=90)
        run(["docker", "cp", f"{container}:{remote_screenshot}", str(local_screenshot)], timeout=60)
        parsed = parse_browserleaks_raw_text(raw_text)
        parsed.update(
            {
                "instance": label,
                "site": "browserleaks-ip",
                "screenshot_path": str(local_screenshot),
                "state_path": str(state_path),
                "raw_text_path": str(raw_text_path),
                "raw_json": state,
            }
        )
        return score_observation(parsed)
    finally:
        browser_use(container, ["open", "https://example.com"], timeout=30, check=False)


def import_state(label: str, state_path: Path, output_dir: Path, screenshot_path: str = "") -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    raw_text = extract_raw_text(state)
    imported_dir = output_dir / f"neko-{label}"
    imported_dir.mkdir(parents=True, exist_ok=True)
    raw_text_path = imported_dir / "browserleaks-state.txt"
    copied_state_path = imported_dir / "browserleaks-state.json"
    raw_text_path.write_text(raw_text, encoding="utf-8")
    copied_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    parsed = parse_browserleaks_raw_text(raw_text)
    parsed.update(
        {
            "instance": label,
            "site": "browserleaks-ip",
            "screenshot_path": screenshot_path,
            "state_path": str(copied_state_path),
            "raw_text_path": str(raw_text_path),
            "raw_json": state,
        }
    )
    return score_observation(parsed)


def render_markdown_report(run_id: str, rows: list[dict[str, Any]], *, generated_at: str | None = None) -> str:
    generated_at = generated_at or dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(rows)
    clean = sum(1 for row in rows if row.get("purity_label") == "clean")
    usable = sum(1 for row in rows if row.get("purity_label") == "usable")
    risky = sum(1 for row in rows if row.get("purity_label") == "risky")
    poor = sum(1 for row in rows if row.get("purity_label") == "poor")
    proxy_yes = sum(1 for row in rows if row.get("proxy_flag") == "yes")
    average = round(sum(int(row.get("purity_score") or 0) for row in rows) / total, 1) if total else 0
    conclusion = "结论：暂无样本。"
    if total and (poor + risky == total or average < 50):
        conclusion = "结论：当前样本整体偏脏，主要风险来自 hosting/datacenter 或隧道化网络画像。"
    elif total and proxy_yes:
        conclusion = "结论：当前样本存在明显代理/机房标记，建议优先更换出口 IP，再继续调浏览器指纹。"
    elif total:
        conclusion = "结论：当前样本没有明显机房代理红旗，但仍建议继续跨站点复核。"

    lines = [
        "# IP 纯净度批量检测报告",
        "",
        f"- 运行 ID：`{run_id}`",
        f"- 生成时间：{generated_at}",
        f"- 样本数：{total}",
        f"- 平均纯净度分：{average}/100",
        f"- 分布：clean={clean}，usable={usable}，risky={risky}，poor={poor}",
        f"- 明显 proxy/hosting 标记：{proxy_yes}/{total}",
        "",
        f"**{conclusion}**",
        "",
        "## 明细表",
        "",
        "| 实例 | IP | 地理位置 | ISP | Usage Type | Proxy 标记 | 分数 | 结论 |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for row in rows:
        instance = f"neko-{row.get('instance', '')}"
        geo = " / ".join(str(x) for x in [row.get("country", ""), row.get("city", "")] if x)
        lines.append(
            "| "
            + " | ".join(
                str(x).replace("|", "\\|")
                for x in [
                    instance,
                    row.get("ip", ""),
                    geo,
                    row.get("isp", ""),
                    row.get("usage_type", ""),
                    row.get("proxy_flag", ""),
                    row.get("purity_score", ""),
                    row.get("purity_label", ""),
                ]
            )
            + " |"
        )
    lines.extend(["", "## 风险解释", ""])
    for row in rows:
        lines.extend(
            [
                f"### neko-{row.get('instance', '')}",
                "",
                f"- IP：`{row.get('ip', '')}`",
                f"- ASN/Network：{row.get('network', '') or '未提取'}",
                f"- Organization：{row.get('organization', '') or '未提取'}",
                f"- Usage Type：{row.get('usage_type', '') or '未提取'}",
                f"- Timezone：{row.get('timezone', '') or '未提取'}",
                f"- 被动 OS：{row.get('passive_os', '') or '未提取'}；UA/CH 平台：{row.get('sec_ch_ua_platform', '') or '未提取'}",
                f"- Link Type：{row.get('link_type', '') or '未提取'}",
                f"- 扣分原因：{row.get('notes', '') or '无明显扣分项'}",
                f"- 截图证据：`{row.get('screenshot_path', '') or '未采集'}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 方法说明",
            "",
            "本报告使用 BrowserLeaks IP 页面抽取浏览器实际出口的网络画像，并本地写入 SQLite。评分是排查用启发式，不等价于任何单一风控站点的官方分数：",
            "",
            "- `Corporate / Hosting`、datacenter、cloud、proxy、VPN 等 usage type 会被视为明显扣分。",
            "- 被动 OS 与浏览器 UA 平台不一致会扣分。",
            "- `IPSec or GRE` 等隧道化链路类型会扣分。",
            "- 浏览器自动化/JS 指纹问题应结合 Pixelscan、Fingerprint.com 等站点另行交叉验证。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_html(markdown_text: str) -> str:
    body = markdown.markdown(markdown_text, extensions=["tables", "fenced_code"]) if markdown else "<pre>" + html.escape(markdown_text) + "</pre>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>IP 纯净度批量检测报告</title>
<style>
  @page {{ size: A4; margin: 16mm; }}
  body {{ font-family: 'Noto Sans CJK SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif; color: #172033; line-height: 1.58; }}
  h1 {{ color: #0f3f8f; border-bottom: 2px solid #d8e6ff; padding-bottom: 8px; }}
  h2 {{ color: #24539f; margin-top: 24px; }}
  h3 {{ color: #2c3e66; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  th, td {{ border: 1px solid #d9e2f2; padding: 6px 8px; vertical-align: top; }}
  th {{ background: #eef5ff; color: #173b78; }}
  code {{ background: #f4f7fb; padding: 1px 4px; border-radius: 4px; }}
  strong {{ color: #0f3f8f; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def write_reports(run_id: str, rows: list[dict[str, Any]], output_dir: Path) -> dict[str, Path]:
    markdown_path = output_dir / "ip-purity-report.md"
    html_path = output_dir / "ip-purity-report.html"
    pdf_path = output_dir / "ip-purity-report.pdf"
    md = render_markdown_report(run_id, rows)
    markdown_path.write_text(md, encoding="utf-8")
    html_path.write_text(render_html(md), encoding="utf-8")
    chromium = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chrome")
    if chromium:
        run([chromium, "--headless", "--no-sandbox", f"--print-to-pdf={pdf_path}", str(html_path)], timeout=120)
    return {"markdown": markdown_path, "html": html_path, "pdf": pdf_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances", type=int, default=1, help="number of neko-cloakbrowser-XX containers to collect live")
    parser.add_argument("--workers", type=int, default=1, help="reserved for future parallel collection; currently collected sequentially for stability")
    parser.add_argument("--wait-seconds", type=int, default=45, help="max seconds to wait for BrowserLeaks result")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="base directory for run artifacts")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--run-id", default="", help="explicit run id; defaults to current timestamp")
    parser.add_argument("--from-state", action="append", default=[], help="import captured state as LABEL=PATH or PATH; can be repeated")
    parser.add_argument("--screenshot", default="", help="screenshot path to attach when importing a single --from-state file")
    parser.add_argument("--no-pdf", action="store_true", help="write Markdown/HTML but skip Chromium PDF export")
    return parser.parse_args()


def state_specs(items: list[str]) -> list[tuple[str, Path]]:
    specs: list[tuple[str, Path]] = []
    for index, item in enumerate(items, start=1):
        if "=" in item:
            label, raw_path = item.split("=", 1)
        else:
            label, raw_path = f"{index:02d}", item
        specs.append((label.zfill(2), Path(raw_path).expanduser().resolve()))
    return specs


def main() -> int:
    args = parse_args()
    run_id = args.run_id or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db).expanduser().resolve()
    init_db(db_path)
    source = "imported-state" if args.from_state else "live-browserleaks"
    create_run(db_path, run_id, source=source)

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    if args.from_state:
        for label, path in state_specs(args.from_state):
            try:
                rows.append(import_state(label, path, output_dir, args.screenshot))
            except Exception as exc:  # noqa: BLE001 - CLI aggregates failures.
                failures.append(f"neko-{label}: {exc}")
    else:
        labels = [f"{i:02d}" for i in range(1, args.instances + 1)]
        for label in labels:
            try:
                rows.append(collect_one(label, output_dir, args.wait_seconds))
            except Exception as exc:  # noqa: BLE001 - CLI aggregates failures and keeps evidence.
                failures.append(f"neko-{label}: {exc}")

    for row in rows:
        insert_observation(db_path, run_id=run_id, observation=row)
    loaded_rows = load_observations(db_path, run_id)
    paths = write_reports(run_id, loaded_rows, output_dir)
    if args.no_pdf:
        paths["pdf"].unlink(missing_ok=True)

    manifest = {
        "run_id": run_id,
        "db_path": str(db_path),
        "output_dir": str(output_dir),
        "artifacts": {key: str(value) for key, value in paths.items() if value.exists()},
        "observations": len(loaded_rows),
        "failures": failures,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
