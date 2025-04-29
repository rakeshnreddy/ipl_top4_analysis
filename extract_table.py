#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timezone

# ── Configuration ────────────────────────────────────────────────────────────────
API_URL     = (
    "https://api.cricapi.com/v1/series_points"
    "?apikey=63d25b78-f287-4cf5-a2f5-4c97396766d5"
    "&id=d5a498c8-7596-4b93-8ab0-e0efc3345312"
)
OUTPUT_FILE = "current_standings.json"

# Map full team names → your short keys
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

def main():
    resp = requests.get(API_URL)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != "success":
        raise RuntimeError("API returned error status")

    records = []
    for item in payload.get("data", []):
        # Extract raw fields
        team_raw = item.get("teamname")
        matches  = item.get("matches", 0)
        wins     = item.get("wins", 0)
        ties     = item.get("ties", 0)
        nr       = item.get("nr", 0)
        # Compute IPL points: Win=2, Tie=1, NR=1
        points   = wins * 2 + ties + nr

        if not team_raw:
            continue

        # Map to your short key
        team = TEAM_NAME_MAP.get(team_raw, team_raw)

        records.append({
            "Team":    team,
            "Matches": matches,
            "Wins":    wins,
            "Points":  points
        })

    # Sort by Points descending
    records.sort(key=lambda r: r["Points"], reverse=True)

    standings = {
        rec["Team"]: {
            "Matches": rec["Matches"],
            "Wins":    rec["Wins"],
            "Points":  rec["Points"]
        }
        for rec in records
    }

    output = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source":       API_URL,
        "standings":    standings
    }

    # Print and write to file
    print(json.dumps(output, indent=4))
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)
    print(f"\n✔ Saved {len(records)} teams to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
