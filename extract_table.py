#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timezone

# ── Configuration ────
API_KEY           = "63d25b78-f287-4cf5-a2f5-4c97396766d5"
SERIES_ID         = "d5a498c8-7596-4b93-8ab0-e0efc3345312"
STANDINGS_URL     = f"https://api.cricapi.com/v1/series_points?apikey={API_KEY}&id={SERIES_ID}"
FIXTURES_URL      = f"https://api.cricapi.com/v1/series_info?apikey={API_KEY}&id={SERIES_ID}"
OUTPUT_STANDINGS  = "current_standings2.json"
OUTPUT_FIXTURES   = "remaining_fixtures2.json"

# Full → short team mapping
TEAM_NAME_MAP = {
    "Royal Challengers Bengaluru": "Bangalore",
    "Mumbai Indians":               "Mumbai",
    "Gujarat Titans":               "Gujarat",
    "Delhi Capitals":               "Delhi",
    "Punjab Kings":                 "Punjab",
    "Lucknow Super Giants":         "Lucknow",
    "Kolkata Knight Riders":        "Kolkata",
    "Rajasthan Royals":             "Rajasthan",
    "Sunrisers Hyderabad":          "Hyderabad",
    "Chennai Super Kings":          "Chennai",
}

def fetch_standings():
    resp = requests.get(STANDINGS_URL)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError("Standings API error")

    records = []
    for item in payload.get("data", []):
        team_raw = item.get("teamname")
        matches  = item.get("matches", 0)
        wins     = item.get("wins", 0)
        ties     = item.get("ties", 0)
        nr       = item.get("nr", 0)
        points   = wins * 2 + ties + nr
        if not team_raw:
            continue
        team = TEAM_NAME_MAP.get(team_raw, team_raw)
        records.append({
            "Team":    team,
            "Matches": matches,
            "Wins":    wins,
            "Points":  points
        })

    records.sort(key=lambda r: r["Points"], reverse=True)
    standings = {
        rec["Team"]: {
            "Matches": rec["Matches"],
            "Wins":    rec["Wins"],
            "Points":  rec["Points"],
        }
        for rec in records
    }

    return {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source":       "Series Points API",
        "standings":    standings
    }

def fetch_fixtures():
    resp = requests.get(FIXTURES_URL)
    resp.raise_for_status()
    payload = resp.json()
    match_list = payload.get("data", {}).get("matchList", [])

    now = datetime.now(timezone.utc)
    upcoming = []

    for match in match_list:
        if match.get("status") != "Match not started" or not match.get("hasSquad", False):
            continue

        dt_str = match.get("dateTimeGMT")
        try:
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        except Exception:
            continue

        if dt < now:
            continue

        teams = match.get("teams", [])
        if len(teams) != 2:
            continue

        t1 = TEAM_NAME_MAP.get(teams[0], teams[0])
        t2 = TEAM_NAME_MAP.get(teams[1], teams[1])
        upcoming.append((dt, [t1, t2]))

    upcoming.sort(key=lambda x: x[0])
    fixtures = [pair for _, pair in upcoming]

    return {
        "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source":       "Series Info API",
        "fixtures":     fixtures
    }

def main():
    standings_json = fetch_standings()
    with open(OUTPUT_STANDINGS, "w", encoding="utf-8") as f:
        json.dump(standings_json, f, indent=4)
    print(f"✔ Saved standings to {OUTPUT_STANDINGS}")

    fixtures_json = fetch_fixtures()
    with open(OUTPUT_FIXTURES, "w", encoding="utf-8") as f:
        json.dump(fixtures_json, f, indent=4)
    print(f"✔ Saved fixtures to {OUTPUT_FIXTURES}")

if __name__ == "__main__":
    main()
