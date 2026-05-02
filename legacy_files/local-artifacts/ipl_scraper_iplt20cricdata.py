#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────────────────
API_URL     = (
    "https://api.cricapi.com/v1/series_info"
    "?apikey=REDACTED_USE_CRICDATA_API_KEY"
    "&id=d5a498c8-7596-4b93-8ab0-e0efc3345312"
)
OUTPUT_FILE = "remaining_fixtures.json"

# Full → short mapping
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
    # 1) Fetch full fixtures
    resp = requests.get(API_URL)
    resp.raise_for_status()
    payload = resp.json()

    match_list = payload.get("data", {}).get("matchList", [])
    upcoming = []

    now = datetime.now(timezone.utc)

    for match in match_list:
        # Only include not-yet-started matches with squads
        if match.get("status") != "Match not started" or not match.get("hasSquad", False):
            continue

        # Parse the match date/time
        dt_str = match.get("dateTimeGMT")
        try:
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        except Exception:
            continue

        # Skip any in the past
        if dt < now:
            continue

        teams = match.get("teams", [])
        if len(teams) != 2:
            continue

        # Map to short names
        t1 = TEAM_NAME_MAP.get(teams[0], teams[0])
        t2 = TEAM_NAME_MAP.get(teams[1], teams[1])

        upcoming.append((dt, [t1, t2]))

    # 2) Sort by date ascending (closest first, farthest last)
    upcoming.sort(key=lambda x: x[0])

    # Extract just the fixtures list
    fixtures = [pair for _, pair in upcoming]

    output = {
        "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source":       "cricapi",
        "fixtures":     fixtures
    }

    # 3) Write to JSON file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"Saved {len(fixtures)} ordered fixtures to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
