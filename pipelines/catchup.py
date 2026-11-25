"""Catch-up: once a day, rerun any feed whose last run failed or whose last success is older than its cadence allows.
Reads data/status.json, dispatches the responsible workflow with `only=<group>` through the GitHub API, waits, and
writes data/catchup.json (kept in the repo, not published)."""
import os, sys, time, json, datetime as dt
import requests
sys.path.insert(0, os.path.dirname(__file__))
from common import DATA, read_json, write_json, now  # noqa: E402

# source -> (workflow file, group, max hours since last success before it counts as late)
FEEDS = {
    "prices": ("daily.yml", "prices", 30), "model_economics": ("daily.yml", "prices", 30), "model_balance": ("daily.yml", "prices", 30),
    "news": ("daily.yml", "news", 30), "policy_fedreg": ("daily.yml", "news", 30), "policy_watch": ("daily.yml", "news", 30),
    "ams_cash": ("weekly.yml", "ams", 8 * 24), "lcfs_ca_weekly": ("weekly.yml", "carb", 8 * 24), "eia_spot": ("weekly.yml", "spot", 8 * 24),
    "epa_emts": ("monthly.yml", "epa", 35 * 24), "lcfs_ca_monthly": ("monthly.yml", "credits", 35 * 24),
    "lcfs_oregon": ("monthly.yml", "credits", 35 * 24), "lcfs_washington": ("monthly.yml", "credits", 35 * 24),
    "eia_feedstocks": ("monthly.yml", "eia", 35 * 24), "eia_capacity": ("monthly.yml", "eia", 35 * 24), "eia_mer": ("monthly.yml", "eia", 35 * 24),
    "wasde": ("monthly.yml", "usda", 35 * 24), "psd": ("monthly.yml", "usda", 35 * 24),
}


def hours_since(t):
    if not t:
        return 1e9
    return (dt.datetime.now(dt.timezone.utc) - dt.datetime.strptime(t, "%Y-%m-%d %H:%M UTC").replace(tzinfo=dt.timezone.utc)).total_seconds() / 3600


def main():
    st = read_json(DATA / "status.json", {}) or {}
    late = {}
    for src, (wf, grp, mx) in FEEDS.items():
        s = st.get(src)
        why = "never run" if not s else ("last run failed" if not s.get("ok") else ("late" if hours_since(s.get("last_ok")) > mx else None))
        if why:
            late.setdefault((wf, grp), []).append(f"{src}: {why}")
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    done = []
    for (wf, grp), why in late.items():
        r = None
        if repo and tok:
            r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/dispatches",
                              headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                              json={"ref": "main", "inputs": {"only": grp}}, timeout=30)
        done.append({"workflow": wf, "group": grp, "why": why, "dispatched": bool(r is not None and r.status_code == 204)})
        time.sleep(2)
    write_json(DATA / "catchup.json", {"checked": now(), "reruns": done})
    print(json.dumps(done, indent=1))


if __name__ == "__main__":
    main()
