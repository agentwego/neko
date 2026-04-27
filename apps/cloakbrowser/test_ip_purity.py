import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("ip-purity.py")
spec = importlib.util.spec_from_file_location("ip_purity", MODULE_PATH)
ip_purity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ip_purity)


def test_parse_browserleaks_raw_text_extracts_network_fields():
    raw = """
[230]<td />
		IP Address
	[232]<td />
		172.121.7.180
[249]<td />
		Country
	[251]<td />
		United States
[262]<td />
		State/Region
	[264]<td />
		California
[270]<td />
		City
	[272]<td />
		Los Angeles
[274]<td />
		ISP
	[275]<td />
		SkyQuantum Internet Service
[279]<td />
		Organization
	[281]<td />
		Skyquantum Internet Service LLC
[285]<td />
		Network
	[287]<td />
		AS55201
		SkyQuantum Internet Service
[293]<td />
		Usage Type
	[295]<td />
		Corporate / Hosting
[299]<td />
		Timezone
	[301]<td />
		America/Los_Angeles
[391]<td />
		OS
	[393]<td />
		Android
[403]<td />
		Link Type
	[405]<td />
		IPSec or GRE
[485]<td />
		Sec-CH-UA-Platform
	[487]<td />
		"Linux"
[497]<td />
		User-Agent
	[499]<td />
		Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/146 Safari/537.36
"""
    parsed = ip_purity.parse_browserleaks_raw_text(raw)
    assert parsed["ip"] == "172.121.7.180"
    assert parsed["country"] == "United States"
    assert parsed["city"] == "Los Angeles"
    assert parsed["isp"] == "SkyQuantum Internet Service"
    assert parsed["organization"] == "Skyquantum Internet Service LLC"
    assert parsed["network"].startswith("AS55201")
    assert parsed["usage_type"] == "Corporate / Hosting"
    assert parsed["timezone"] == "America/Los_Angeles"
    assert parsed["passive_os"] == "Android"
    assert parsed["link_type"] == "IPSec or GRE"
    assert parsed["sec_ch_ua_platform"] == '"Linux"'
    assert "Linux x86_64" in parsed["user_agent"]


def test_score_observation_penalizes_hosting_and_passive_mismatch():
    observation = {
        "ip": "172.121.7.180",
        "usage_type": "Corporate / Hosting",
        "passive_os": "Android",
        "link_type": "IPSec or GRE",
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/146 Safari/537.36",
    }
    scored = ip_purity.score_observation(observation)
    assert scored["proxy_flag"] == "yes"
    assert scored["purity_score"] == 20
    assert scored["purity_label"] == "poor"
    assert "hosting/datacenter" in scored["notes"]
    assert "passive OS mismatch" in scored["notes"]


def test_sqlite_roundtrip_records_observation(tmp_path):
    db_path = tmp_path / "ip-purity.sqlite3"
    run_id = "test-run"
    ip_purity.init_db(db_path)
    ip_purity.insert_observation(
        db_path,
        run_id=run_id,
        observation={
            "instance": "01",
            "site": "browserleaks-ip",
            "ip": "172.121.7.180",
            "usage_type": "Corporate / Hosting",
            "purity_score": 20,
            "purity_label": "poor",
            "screenshot_path": "/tmp/shot.png",
            "state_path": "/tmp/state.json",
        },
    )
    rows = ip_purity.load_observations(db_path, run_id)
    assert len(rows) == 1
    assert rows[0]["instance"] == "01"
    assert rows[0]["ip"] == "172.121.7.180"
    assert rows[0]["purity_label"] == "poor"


def test_score_observation_keeps_passive_mismatch_below_clean():
    observation = {
        "ip": "172.56.140.108",
        "usage_type": "Cellular",
        "passive_os": "Android",
        "link_type": "",
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/146 Safari/537.36",
    }
    scored = ip_purity.score_observation(observation)
    assert scored["purity_score"] == 80
    assert scored["purity_label"] == "usable"
    assert scored["proxy_flag"] == "no"
    assert "passive OS mismatch" in scored["notes"]


def test_render_markdown_contains_summary_table():
    rows = [
        {
            "instance": "01",
            "ip": "172.121.7.180",
            "country": "United States",
            "city": "Los Angeles",
            "isp": "SkyQuantum Internet Service",
            "usage_type": "Corporate / Hosting",
            "proxy_flag": "yes",
            "purity_score": 20,
            "purity_label": "poor",
            "passive_os": "Android",
            "link_type": "IPSec or GRE",
            "screenshot_path": "/tmp/shot.png",
        }
    ]
    md = ip_purity.render_markdown_report("run-1", rows, generated_at="2026-04-27 14:00:00")
    assert "# IP 纯净度批量检测报告" in md
    assert "| neko-01 | 172.121.7.180 | United States / Los Angeles | SkyQuantum Internet Service | Corporate / Hosting | yes | 20 | poor |" in md
    assert "结论：当前样本整体偏脏" in md
