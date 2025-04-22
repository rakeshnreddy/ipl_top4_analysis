# generate_ipl_data.py
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import os
import traceback # Import traceback for detailed error printing

# --- Configuration ---
# Option 1: Scrape Live Data (Requires internet, fragile)
SCRAPE_LIVE_DATA = True # Set to False to use hardcoded data below

# --- !!! IMPORTANT URLS !!! ---
# Select the season you want data for.
# For the most RECENTLY COMPLETED season (2025):
CURRENT_SEASON_YEAR = "2025"
CURRENT_SEASON_ID = "1449924"
# For the UPCOMING season (2025) - NOTE: Data will likely be unavailable until the season starts!
# CURRENT_SEASON_YEAR = "2025"
# CURRENT_SEASON_ID = "1449924" # Example ID, might change

STANDINGS_URL = f"https://www.espncricinfo.com/series/ipl-{CURRENT_SEASON_YEAR}-{CURRENT_SEASON_ID}/points-table-standings"
FIXTURES_URL = f"https://www.espncricinfo.com/series/ipl-{CURRENT_SEASON_YEAR}-{CURRENT_SEASON_ID}/match-schedule-fixtures-and-results"
# --- End Important URLs ---

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'} # Mimic a browser

# Option 2: Hardcoded Data (Use as fallback or for testing if scraping fails)
# These should match the structure expected by the analysis apps
HARDCODED_STANDINGS = {
    # Example structure - replace with actual data if needed (e.g., final 2024 standings)
    'Kolkata': {'Matches': 14, 'Wins': 9, 'Points': 20}, # Example NRR tiebreak might put KKR higher
    'Hyderabad': {'Matches': 14, 'Wins': 8, 'Points': 17},
    'Rajasthan': {'Matches': 14, 'Wins': 8, 'Points': 17},
    'Bangalore': {'Matches': 14, 'Wins': 7, 'Points': 14}, # Example NRR tiebreak
    'Chennai': {'Matches': 14, 'Wins': 7, 'Points': 14},
    'Delhi': {'Matches': 14, 'Wins': 7, 'Points': 14},
    'Lucknow': {'Matches': 14, 'Wins': 7, 'Points': 14},
    'Gujarat': {'Matches': 14, 'Wins': 5, 'Points': 12},
    'Punjab': {'Matches': 14, 'Wins': 5, 'Points': 10},
    'Mumbai': {'Matches': 14, 'Wins': 4, 'Points': 8}
}

HARDCODED_FIXTURES = [
    # Example: If the season was over, this would be empty
]

# Mapping from scraped names (lowercase, simplified) to your internal keys
# **IMPORTANT**: You MUST update this mapping based on the exact names scraped from the site!
TEAM_NAME_MAPPING = {
    'rajasthan royals': 'Rajasthan',
    'kolkata knight riders': 'Kolkata',
    'lucknow super giants': 'Lucknow',
    'sunrisers hyderabad': 'Hyderabad',
    'chennai super kings': 'Chennai',
    'delhi capitals': 'Delhi',
    'punjab kings': 'Punjab',
    'gujarat titans': 'Gujarat',
    'mumbai indians': 'Mumbai',
    'royal challengers bengaluru': 'Bangalore',
    'rc bengaluru': 'Bangalore', # Add variations as needed
    # Add any other variations found during testing
}

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__)) # Save in the same directory as the script
OUTPUT_STANDINGS_FILE = os.path.join(OUTPUT_DIR, 'current_standings.json')
OUTPUT_FIXTURES_FILE = os.path.join(OUTPUT_DIR, 'remaining_fixtures.json')
# --- End Configuration ---

def sanitize_team_name(name):
    """Cleans and standardizes team names for mapping."""
    return name.lower().strip()

def get_internal_team_key(scraped_name):
    """Maps scraped name to internal key using TEAM_NAME_MAPPING."""
    sanitized = sanitize_team_name(scraped_name)
    key = TEAM_NAME_MAPPING.get(sanitized)
    if not key:
        # Attempt partial matching (optional, can be risky)
        partial_match = None
        for map_key, internal_key in TEAM_NAME_MAPPING.items():
             # Check if sanitized name contains a known part OR if a known name is part of the sanitized one
             if (sanitized in map_key and len(sanitized) > 3) or \
                (map_key in sanitized and len(map_key) > 3) :
                 partial_match = internal_key
                 break # Take the first partial match
        if partial_match:
             print(f"WARNING: Unmapped team name: '{scraped_name}'. Using partial match: '{partial_match}' based on '{map_key}'")
             return partial_match
        else:
             print(f"ERROR: Could not map team name: '{scraped_name}' (Sanitized: '{sanitized}'). Update TEAM_NAME_MAPPING.")
             return None # Return None if no mapping found
    return key

def fetch_standings_from_web():
    """Scrapes and parses the IPL points table from the web."""
    print(f"Attempting to fetch live standings from {STANDINGS_URL}...")
    try:
        response = requests.get(STANDINGS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status() # Raise an exception for bad status codes
        soup = BeautifulSoup(response.text, 'html.parser')

        standings = {}
        # --- !!! SELECTOR CHECK NEEDED !!! ---
        # **IMPORTANT**: Inspect the standings page HTML and update this selector if needed.
        table = soup.find('table', class_=re.compile(r'ds-w-full.*ds-table.*standings'))
        # --- End Selector Check ---

        if not table:
            print(f"ERROR: Could not find the standings table using the specified selector pattern on {STANDINGS_URL}. Website structure might have changed.")
            return None

        tbody = table.find('tbody')
        if not tbody:
            print("ERROR: Could not find tbody in the standings table.")
            return None

        rows = tbody.find_all('tr')
        if not rows:
            print("ERROR: Could not find rows (tr) in the standings table tbody.")
            return None

        print(f"Found {len(rows)} rows in standings table. Parsing...")
        parsed_count = 0
        for i, row in enumerate(rows):
            cols = row.find_all('td')
            # Expecting columns like: Team, M, W, L, T, NR, Pts, NRR etc. Check the actual table.
            if len(cols) > 6: # Need at least Team, M, W, L, T, N/R, Pts
                # --- !!! SELECTOR CHECK NEEDED !!! ---
                # **IMPORTANT**: Inspect the team name element and update this selector if needed.
                team_name_tag = cols[0].find('span', class_=re.compile(r'ds-text-tight-s'))
                # --- End Selector Check ---

                if not team_name_tag:
                    print(f"Skipping row {i+1}, couldn't find team name span with expected class.")
                    continue # Skip header/empty rows

                scraped_name = team_name_tag.get_text(strip=True)
                team_key = get_internal_team_key(scraped_name)
                if not team_key:
                    print(f"Skipping row {i+1} for team '{scraped_name}' due to mapping failure.")
                    continue # Skip if team name couldn't be mapped

                try:
                    # --- !!! COLUMN INDEX CHECK NEEDED !!! ---
                    # **IMPORTANT**: Verify these column indices match the live table structure.
                    matches_str = cols[1].get_text(strip=True)
                    wins_str = cols[2].get_text(strip=True)
                    points_str = cols[6].get_text(strip=True)
                    # --- End Column Index Check ---

                    matches = int(matches_str)
                    wins = int(wins_str)
                    points = int(points_str)

                except (ValueError, IndexError) as e:
                    print(f"ERROR: Could not parse data for {scraped_name} in row {i+1}: M='{matches_str}', W='{wins_str}', Pts='{points_str}'. Error: {e}")
                    print(f"       Row HTML snippet: {row.prettify()[:200]}...") # Print snippet for debugging
                    continue

                standings[team_key] = {'Matches': matches, 'Wins': wins, 'Points': points}
                parsed_count += 1
            # else:
            #     print(f"Skipping row {i+1} with insufficient columns: {len(cols)}")


        if not standings:
             print("ERROR: No standings data could be extracted after parsing rows. Check selectors and team mapping.")
             return None

        if parsed_count != len(TEAM_NAME_MAPPING):
             print(f"WARNING: Parsed standings for {parsed_count} teams, but expected {len(TEAM_NAME_MAPPING)}. Some teams might be missing or unmapped.")

        print(f"Successfully parsed standings for {parsed_count} teams from web.")
        return standings

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error fetching standings from {STANDINGS_URL}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error parsing standings: {e}")
        traceback.print_exc() # Print detailed traceback for debugging
        return None


def fetch_fixtures_from_web():
    """Scrapes and parses the remaining IPL fixtures from the web."""
    print(f"Attempting to fetch live fixtures from {FIXTURES_URL}...")
    try:
        response = requests.get(FIXTURES_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        remaining_fixtures = []
        # --- !!! SELECTOR CHECK NEEDED !!! ---
        # **IMPORTANT**: Inspect the fixtures page HTML and update this selector to find individual match containers.
        # This is highly likely to need adjustment. Try inspecting a few match divs.
        primary_selector = re.compile(r'ds-p-4.*ds-border-b.*ds-border-line.*ds-relative')
        fallback_selector = re.compile(r'ci-match-card') # Add other potential patterns if needed

        match_divs = soup.find_all('div', class_=primary_selector)
        if not match_divs:
             print(f"Primary match container selector ('{primary_selector.pattern}') failed. Trying fallback ('{fallback_selector.pattern}')...")
             match_divs = soup.find_all('div', class_=fallback_selector)
             if not match_divs:
                  print(f"ERROR: Could not find match containers using known selectors on {FIXTURES_URL}. Website structure might have changed.")
                  return None # Return None to indicate failure
        # --- End Selector Check ---


        print(f"Found {len(match_divs)} potential match containers. Parsing for upcoming fixtures...")
        processed_count = 0
        skipped_completed = 0
        skipped_mapping = 0
        skipped_parsing = 0

        for i, match_div in enumerate(match_divs):
            # --- !!! LOGIC & SELECTOR CHECK NEEDED !!! ---
            # **IMPORTANT**: Inspect upcoming vs completed matches and update status/result selectors and logic.
            status_tags = match_div.find_all('span', class_=re.compile(r'ds-text-tight-xs.*ds-font-bold.*ds-uppercase')) # Example status selector
            result_tag = match_div.find('p', class_=re.compile(r'ds-text-tight-s.*ds-truncate.*ds-text-typo-title')) # Example result selector
            # Alternative: Look for score elements? Date/time elements?
            # --- End Logic & Selector Check ---

            is_upcoming = False
            status_text = ""
            result_text = ""

            if status_tags:
                 status_text = " | ".join(tag.get_text(strip=True).lower() for tag in status_tags)
            if result_tag:
                 result_text = result_tag.get_text(strip=True).lower()

            # Refined Logic: Assume upcoming if NO explicit result keywords are found.
            # Add more keywords if needed based on inspection.
            result_keywords = ['result', 'live', 'abandoned', 'complete', 'won', 'lost', 'tied', 'no result', 'match drawn']
            if not any(kw in status_text for kw in result_keywords) and \
               not any(kw in result_text for kw in result_keywords):
                 is_upcoming = True

            # Debug print (optional, remove for production)
            # print(f"Match Div {i+1}: Status='{status_text}', Result='{result_text}', Upcoming={is_upcoming}")

            if is_upcoming:
                # --- !!! SELECTOR CHECK NEEDED !!! ---
                # **IMPORTANT**: Inspect team name elements within a match div and update selector.
                team_tags = match_div.find_all('p', class_=re.compile(r'ds-text-tight-m.*ds-font-bold.*ds-capitalize')) # Example team name selector
                # --- End Selector Check ---

                if len(team_tags) >= 2:
                    # Handle potential extra tags; assume first two are teams
                    scraped_team_a = team_tags[0].get_text(strip=True)
                    scraped_team_b = team_tags[1].get_text(strip=True)

                    team_a_key = get_internal_team_key(scraped_team_a)
                    team_b_key = get_internal_team_key(scraped_team_b)

                    if team_a_key and team_b_key:
                        remaining_fixtures.append((team_a_key, team_b_key))
                        processed_count += 1
                    else:
                        print(f"Skipping upcoming fixture {i+1} due to unmapped teams: '{scraped_team_a}' vs '{scraped_team_b}'")
                        skipped_mapping += 1
                else:
                     print(f"Skipping potential upcoming fixture {i+1}: Not enough team names found (found {len(team_tags)}). Check team name selector.")
                     print(f"       Match Div HTML snippet: {match_div.prettify()[:200]}...") # Print snippet for debugging
                     skipped_parsing += 1
            else:
                 skipped_completed += 1

        print(f"Parsed {processed_count} upcoming fixtures.")
        if skipped_completed > 0: print(f"Skipped {skipped_completed} completed/live matches.")
        if skipped_mapping > 0: print(f"Skipped {skipped_mapping} fixtures due to unmapped team names.")
        if skipped_parsing > 0: print(f"Skipped {skipped_parsing} potential fixtures due to parsing issues (e.g., missing team names).")

        # Even if no fixtures are found (e.g., end of season), return an empty list, not None
        return remaining_fixtures

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error fetching fixtures from {FIXTURES_URL}: {e}")
        return None # Indicate failure to fetch
    except Exception as e:
        print(f"ERROR: Unexpected error parsing fixtures: {e}")
        traceback.print_exc() # Print detailed traceback for debugging
        return None # Indicate failure to parse

def save_data(data, filename):
    """Saves data to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Data successfully saved to {filename}")
        return True
    except IOError as e:
        print(f"ERROR: Could not write data to {filename}: {e}")
        return False
    except TypeError as e:
         print(f"ERROR: Could not serialize data to JSON for {filename}: {e}")
         return False

if __name__ == "__main__":
    print(f"--- Starting IPL Data Generation: {datetime.now()} ---")
    print(f"--- Target Season: {CURRENT_SEASON_YEAR} ---")

    final_standings = None
    final_fixtures = None
    source = "Unknown"
    fetch_successful = False

    if SCRAPE_LIVE_DATA:
        print("\nAttempting to scrape live data...")
        # --- Check if target season is in the future ---
        current_year = datetime.now().year
        try:
            target_year_int = int(CURRENT_SEASON_YEAR)
            if target_year_int > current_year:
                 print(f"WARNING: Target season {CURRENT_SEASON_YEAR} is in the future. Live data is likely unavailable.")
                 print("         Attempting scrape anyway, but expect potential errors or empty results.")
            elif target_year_int < current_year:
                 print(f"INFO: Target season {CURRENT_SEASON_YEAR} is a past season.")

        except ValueError:
             print(f"WARNING: Could not parse CURRENT_SEASON_YEAR ('{CURRENT_SEASON_YEAR}') as integer.")


        live_standings = fetch_standings_from_web()
        live_fixtures = fetch_fixtures_from_web()

        # Use live data only if BOTH were fetched successfully (returned data, not None)
        if live_standings is not None and live_fixtures is not None:
            print("\nSuccessfully fetched data structures from web (standings might be empty if season hasn't started).")
            final_standings = live_standings
            final_fixtures = live_fixtures
            source = f"Live Scrape ({CURRENT_SEASON_YEAR})"
            fetch_successful = True # Mark fetch as successful
        else:
            print("\nScraping live data FAILED or returned incomplete data.")
            if live_standings is None: print("Reason: Failed to fetch/parse standings (check errors above).")
            if live_fixtures is None: print("Reason: Failed to fetch/parse fixtures (check errors above).")

            # Fallback only if scraping was attempted and failed
            print("Falling back to hardcoded data.")
            final_standings = HARDCODED_STANDINGS
            final_fixtures = HARDCODED_FIXTURES
            source = "Hardcoded Fallback"
            fetch_successful = False

    else:
        print("\nUsing hardcoded data as configured (SCRAPE_LIVE_DATA = False).")
        final_standings = HARDCODED_STANDINGS
        final_fixtures = HARDCODED_FIXTURES
        source = "Hardcoded Configured"
        fetch_successful = True # Hardcoded is considered "successful" for validation purposes

    # --- Validation ---
    valid = True
    print("\nValidating final data structure...")
    if not isinstance(final_standings, dict): # Allow empty dict if season hasn't started
        print("ERROR: Final standings data is not a dictionary.")
        valid = False
    elif not final_standings and fetch_successful and source != "Hardcoded Configured":
         print("WARNING: Final standings dictionary is empty. This might be expected if the season hasn't started or scraping failed partially.")
         # Allow empty standings if fetch was marked successful (might be pre-season)
    else:
        for team, stats in final_standings.items():
            if not isinstance(stats, dict) or not all(k in stats for k in ['Matches', 'Wins', 'Points']):
                print(f"ERROR: Invalid stats format for team {team} in final standings: {stats}")
                valid = False
                break

    if not isinstance(final_fixtures, list):
        print("ERROR: Final fixtures data is not a list.")
        valid = False
    else:
        # Allow empty fixtures list
        for i, match in enumerate(final_fixtures):
            if not isinstance(match, (list, tuple)) or len(match) != 2:
                print(f"ERROR: Invalid match format found in final fixtures at index {i}: {match}")
                valid = False
                break
            # Check if teams in fixtures exist in standings (only if standings are not empty)
            if final_standings and (match[0] not in final_standings or match[1] not in final_standings):
                 print(f"ERROR: Team(s) in fixture {match} at index {i} not found in final standings keys.")
                 valid = False
                 # Don't break here, report all missing teams

    # --- Save Data ---
    if valid:
        print(f"\nData validation successful. Data source: {source}")
        standings_saved = save_data({
            "last_updated": datetime.now().isoformat(),
            "source": source,
            "standings": final_standings
        }, OUTPUT_STANDINGS_FILE)

        fixtures_saved = save_data({
            "last_updated": datetime.now().isoformat(),
            "source": source,
            "fixtures": final_fixtures
        }, OUTPUT_FIXTURES_FILE)

        if standings_saved and fixtures_saved:
            print("\nData generation completed successfully.")
        else:
            print("\nData generation completed with errors (failed to save one or both files).")
    else:
        print("\nData generation failed due to invalid data structure after processing. Files not saved.")
        print(f"Data source was: {source}")


    print(f"\n--- IPL Data Generation Finished: {datetime.now()} ---")
