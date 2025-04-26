import streamlit as st
from itertools import product
from pandas import DataFrame
import random
import json
import os
from datetime import datetime
import time # Added for progress bar
import altair as alt # <<< ADD THIS IMPORT >>>
import traceback # Added for detailed error printing


# --- Configuration ---
EXHAUSTIVE_LIMIT = 20  # Max fixtures for exhaustive simulation
NUM_SIMULATIONS_MC = 500000 # Number of simulations for Monte Carlo
MC_TOLERANCE = 0.02 # Tolerance for 'Result doesn't matter' in MC (e.g., 2% difference) # <<< ADD THIS
# --- End Configuration ---

# --- File Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STANDINGS_FILE = os.path.join(BASE_DIR, 'current_standings.json')
FIXTURES_FILE = os.path.join(BASE_DIR, 'remaining_fixtures.json')
# ---

# Team colors and full names (Keep as is)
# --- Team Names and Styles ---
team_full_names = {
    'Rajasthan': 'Rajasthan Royals', 'Kolkata': 'Kolkata Knight Riders', 'Lucknow': 'Lucknow Super Giants',
    'Hyderabad': 'Sunrisers Hyderabad', 'Chennai': 'Chennai Super Kings', 'Delhi': 'Delhi Capitals',
    'Punjab': 'Punjab Kings', 'Gujarat': 'Gujarat Titans', 'Mumbai': 'Mumbai Indians',
    'Bangalore': 'Royal Challengers Bangalore'
}

team_short_names = { # Still needed for chart
    'Rajasthan': 'RR', 'Kolkata': 'KKR', 'Lucknow': 'LSG', 'Hyderabad': 'SRH',
    'Chennai': 'CSK', 'Delhi': 'DC', 'Punjab': 'PBKS', 'Gujarat': 'GT',
    'Mumbai': 'MI', 'Bangalore': 'RCB'
}

# Revised styles for better contrast and uniqueness
team_styles = {
    # Team Key: {'bg': 'background_hex', 'text': 'text_hex'}
    'Rajasthan': {'bg': '#FFC0CB', 'text': '#000000'},  # Pink bg, Black text
    'Kolkata':   {'bg': '#3A225D', 'text': '#FFFFFF'},  # Purple bg, White text
    'Lucknow':   {'bg': '#00AEEF', 'text': '#000000'},  # Light Blue bg, Black text
    'Hyderabad': {'bg': '#FF822A', 'text': '#000000'},  # Orange bg, Black text
    'Chennai':   {'bg': '#FDB913', 'text': '#000000'},  # Yellow bg, Black text
    'Delhi':     {'bg': '#004C93', 'text': '#FFFFFF'},  # Dark Blue bg, White text
    'Punjab':    {'bg': '#AF0000', 'text': '#FFFFFF'},  # Darker Red bg, White text (Unique from RCB)
    'Gujarat':   {'bg': '#1C2C5B', 'text': '#FFFFFF'},  # Navy bg, White text
    'Mumbai':    {'bg': '#006CB7', 'text': '#FFFFFF'},  # Blue bg, White text
    'Bangalore': {'bg': '#D11F2D', 'text': '#FFD700'}   # Red bg, Gold text (Unique)
}

# Reverse mapping from FULL name to key (used in row styling)
full_name_key_mapping = {v: k for k, v in team_full_names.items()}
# --- End Team Names and Styles ---



# --- <<< ADD TEAM COLORS >>> ---
team_colors = {
    'Rajasthan': '#FFC0CB',  # Pink
    'Kolkata': '#3A225D',    # Purple
    'Lucknow': '#0078AD',    # Light Blue / Teal
    'Hyderabad': '#FF822A',  # Orange
    'Chennai': '#FFFF00',    # Yellow
    'Delhi': '#004C93',      # Dark Blue
    'Punjab': '#DD1F2D',      # Red
    'Gujarat': '#1C2C5B',    # Dark Blue / Navy
    'Mumbai': '#006CB7',      # Blue
    'Bangalore': '#D11F2D'     # Red/Black - Using Red
}
# --- <<< END TEAM COLORS >>> ---

# --- <<< ADD REVERSE MAPPING HERE >>> ---
team_key_mapping = {v: k for k, v in team_full_names.items()}
# --- <<< END REVERSE MAPPING >>> ---
# --- <<< MODIFY STYLING FUNCTION (Place outside main) >>> ---
def style_team_row(row):
    """Applies background color to the entire row based on team full name,
       allowing Streamlit to handle text color for theme compatibility."""
    team_name = row['Team Name'] # Use the 'Team Name' column (full name)
    team_key = full_name_key_mapping.get(team_name) # Use full name mapping
    style_dict = team_styles.get(team_key) # Get dict containing 'bg'

    if style_dict and 'bg' in style_dict:
        # Only set background-color
        style_string = f"background-color: {style_dict['bg']};"
        return [style_string] * len(row)
    else:
        # Default style if team not found
        return [''] * len(row)
# --- <<< END MODIFICATION >>> ---

# --- Fallback Data (Keep as is) ---
FALLBACK_STANDINGS = {
    'Gujarat':   {'Matches': 8, 'Wins': 6, 'Points': 12}, 'Delhi':     {'Matches': 8, 'Wins': 6, 'Points': 12},
    'Bangalore': {'Matches': 9, 'Wins': 6, 'Points': 12},  'Punjab':    {'Matches': 9, 'Wins': 5, 'Points': 11},
    'Mumbai':    {'Matches': 9, 'Wins': 5, 'Points': 10},  'Lucknow':   {'Matches': 9, 'Wins': 5, 'Points': 10},
    'Kolkata':   {'Matches': 9, 'Wins': 3, 'Points': 7}, 'Hyderabad': {'Matches': 9, 'Wins': 3, 'Points': 6},
    'Rajasthan': {'Matches': 9, 'Wins': 2, 'Points': 4}, 'Chennai':   {'Matches': 9, 'Wins': 2, 'Points': 4}
}
FALLBACK_FIXTURES = [
    ('Mumbai', 'Lucknow'), ('Delhi', 'Bangalore'), ('Rajasthan', 'Gujarat'), ('Delhi', 'Kolkata'),
    ('Chennai', 'Punjab'), ('Rajasthan', 'Mumbai'), ('Gujarat', 'Hyderabad'), ('Bangalore', 'Chennai'), ('Kolkata', 'Rajasthan'),
    ('Punjab', 'Lucknow'), ('Hyderabad', 'Delhi'), ('Mumbai', 'Gujarat'), ('Kolkata', 'Chennai'), ('Punjab', 'Delhi'),
    ('Lucknow', 'Bangalore'), ('Hyderabad', 'Kolkata'), ('Punjab', 'Mumbai'), ('Delhi', 'Gujarat'), ('Chennai', 'Rajasthan'),
    ('Bangalore', 'Hyderabad'), ('Gujarat', 'Lucknow'), ('Mumbai', 'Delhi'), ('Rajasthan', 'Punjab'), ('Bangalore', 'Kolkata'),
    ('Gujarat', 'Chennai'), ('Lucknow', 'Hyderabad')
]
# --- End Fallback Data ---

# --- Data Loading Function (Modified with Stricter Validation) ---
@st.cache_data(ttl=3600)
def load_data():
    """Loads standings and fixtures from JSON files, using fallbacks if necessary,
       and performs strict validation on standings data."""
    loaded_standings = None
    loaded_fixtures = None
    standings_meta = {"source": "Unknown", "last_updated": "N/A"}
    fixtures_meta = {"source": "Unknown", "last_updated": "N/A"}
    load_errors = []

    # Load Standings
    try:
        if os.path.exists(STANDINGS_FILE):
            with open(STANDINGS_FILE, 'r') as f:
                data = json.load(f)
                loaded_standings = data.get("standings")
                standings_meta["source"] = data.get("source", "JSON File")
                standings_meta["last_updated"] = data.get("last_updated", "N/A")
                # Basic check if standings exist in the file
                if loaded_standings is None:
                     load_errors.append(f"Warning: 'standings' key missing in {STANDINGS_FILE}.")
                elif not isinstance(loaded_standings, dict):
                    load_errors.append(f"Warning: Standings data in {STANDINGS_FILE} is not a dictionary.")
                    loaded_standings = None # Treat as invalid
                elif not loaded_standings:
                     load_errors.append(f"Info: Standings data in {STANDINGS_FILE} is empty.")
                     # Keep empty dict for now, validation will handle it
        else:
            load_errors.append(f"Info: Standings file not found: {STANDINGS_FILE}. Using fallback.")
    except (json.JSONDecodeError, IOError) as e:
        load_errors.append(f"Error loading {STANDINGS_FILE}: {e}. Using fallback.")
        loaded_standings = None
    except Exception as e:
        load_errors.append(f"Unexpected error loading standings: {e}. Using fallback.")
        loaded_standings = None

    # Load Fixtures (Keep existing logic)
    try:
        if os.path.exists(FIXTURES_FILE):
            with open(FIXTURES_FILE, 'r') as f:
                data = json.load(f)
                raw_fixtures = data.get("fixtures")
                if isinstance(raw_fixtures, list):
                     loaded_fixtures = [tuple(match) for match in raw_fixtures if isinstance(match, (list, tuple)) and len(match) == 2]
                     if len(loaded_fixtures) != len(raw_fixtures):
                          load_errors.append(f"Warning: Some fixture entries in {FIXTURES_FILE} were invalid or filtered.")
                else:
                     loaded_fixtures = None # Invalid format
                fixtures_meta["source"] = data.get("source", "JSON File")
                fixtures_meta["last_updated"] = data.get("last_updated", "N/A")
                if loaded_fixtures is None and isinstance(raw_fixtures, list): # Check if it was a list but empty/invalid items
                     load_errors.append(f"Warning: Fixtures data in {FIXTURES_FILE} is empty or contained only invalid entries.")
                elif loaded_fixtures is None: # Not a list at all
                     load_errors.append(f"Warning: Fixtures data in {FIXTURES_FILE} is not a list or missing 'fixtures' key.")

        else:
            load_errors.append(f"Info: Fixtures file not found: {FIXTURES_FILE}. Using fallback.")
    except (json.JSONDecodeError, IOError) as e:
        load_errors.append(f"Error loading {FIXTURES_FILE}: {e}. Using fallback.")
        loaded_fixtures = None
    except Exception as e:
        load_errors.append(f"Unexpected error loading fixtures: {e}. Using fallback.")
        loaded_fixtures = None

    # Apply Fallbacks
    final_standings_raw = loaded_standings if loaded_standings is not None else FALLBACK_STANDINGS
    final_fixtures_raw = loaded_fixtures if loaded_fixtures is not None else FALLBACK_FIXTURES

    # --- <<< START: Stricter Standings Validation >>> ---
    validated_standings = {}
    required_keys = {'Matches', 'Wins', 'Points'}

    if isinstance(final_standings_raw, dict):
        for team, stats in final_standings_raw.items():
            if not isinstance(stats, dict):
                load_errors.append(f"ERROR: Data for team '{team}' in standings is not a dictionary. Skipping team.")
                continue # Skip this team

            if not required_keys.issubset(stats.keys()):
                missing = required_keys - stats.keys()
                load_errors.append(f"ERROR: Team '{team}' in standings is missing required keys: {missing}. Skipping team.")
                continue # Skip this team

            # Try converting required values to integers
            try:
                validated_stats = {
                    'Matches': int(stats['Matches']),
                    'Wins': int(stats['Wins']),
                    'Points': int(stats['Points'])
                }
                # Copy over any other existing keys (like probabilities if they were somehow loaded)
                for k, v in stats.items():
                    if k not in validated_stats:
                        validated_stats[k] = v

                validated_standings[team] = validated_stats # Add validated data

            except (ValueError, TypeError) as e:
                load_errors.append(f"ERROR: Non-integer or invalid value found for required keys in team '{team}'. Error: {e}. Skipping team.")
                # Example: stats might be {'Matches': 10, 'Wins': 5, 'Points': 'None'} -> TypeError
                # Example: stats might be {'Matches': 10, 'Wins': 5, 'Points': 'abc'} -> ValueError
                continue # Skip this team
    else:
        load_errors.append("CRITICAL ERROR: Standings data (loaded or fallback) is not a dictionary. Using empty standings.")
        validated_standings = {} # Ensure it's an empty dict if the source was totally invalid

    final_standings = validated_standings # Use the validated data from now on
    # --- <<< END: Stricter Standings Validation >>> ---


    # Determine overall source and timestamp (using original load status)
    if loaded_standings is not None and loaded_fixtures is not None:
        data_source = f"JSON ({standings_meta['source']})"
        last_updated = max(standings_meta['last_updated'], fixtures_meta['last_updated']) if standings_meta['last_updated'] != "N/A" and fixtures_meta['last_updated'] != "N/A" else (standings_meta['last_updated'] if standings_meta['last_updated'] != "N/A" else fixtures_meta['last_updated'])
    elif loaded_standings is not None:
        data_source = f"JSON Standings ({standings_meta['source']}) / Fallback Fixtures"
        last_updated = standings_meta['last_updated']
    elif loaded_fixtures is not None:
        data_source = f"Fallback Standings / JSON Fixtures ({fixtures_meta['source']})"
        last_updated = fixtures_meta['last_updated']
    else:
        data_source = "Fallback Data"
        last_updated = "N/A"


    # --- Fixture Validation (Depends on validated standings) ---
    missing_teams_in_fixtures = set()
    valid_fixtures = []
    # Use the raw fixtures list before validation for this check
    if isinstance(final_fixtures_raw, list):
        for team1, team2 in final_fixtures_raw:
             # Check against the KEYS of the *validated* standings
            valid_match = True
            if team1 not in final_standings: # Check against validated keys
                missing_teams_in_fixtures.add(team1)
                valid_match = False
            if team2 not in final_standings: # Check against validated keys
                missing_teams_in_fixtures.add(team2)
                valid_match = False

            if valid_match:
                valid_fixtures.append((team1, team2)) # Only add fixtures where both teams are valid
    else:
         load_errors.append("ERROR: Fixtures data (loaded or fallback) is not a list. Using empty fixtures.")
         valid_fixtures = [] # Ensure it's an empty list if source was invalid

    if missing_teams_in_fixtures:
        load_errors.append(f"ERROR: Teams found in fixtures but MISSING from validated standings: {missing_teams_in_fixtures}. Associated fixtures ignored.")

    final_fixtures = valid_fixtures # Use only the fixtures with valid teams
    # --- End Fixture Validation ---

    # Final check if standings became empty after validation
    if not final_standings and isinstance(final_standings_raw, dict) and final_standings_raw:
         load_errors.append("CRITICAL ERROR: All teams failed validation. Standings are empty.")

    return final_standings, final_fixtures, last_updated, data_source, load_errors


# --- Helper Functions (Keep calculate_total_matches_per_team, plot_standings as is) ---
def calculate_total_matches_per_team(standings_data, fixtures_data):
    """Calculates total matches based on provided standings and fixtures."""
    if not standings_data: return {}
    total_matches = {team: stats.get('Matches', 0) for team, stats in standings_data.items()}
    for team1, team2 in fixtures_data:
        if team1 in total_matches: total_matches[team1] += 1
        if team2 in total_matches: total_matches[team2] += 1
    return total_matches

def plot_standings(standings_data):
    """Plots standings from a dictionary, using full names, adding position, and ensuring probability columns exist if needed."""
    if not standings_data: return DataFrame()
    df = DataFrame(standings_data).T

    # Ensure essential columns exist
    for col in ['Matches', 'Wins', 'Points']:
        if col not in df.columns: df[col] = 0
    df = df.astype({'Matches': 'int', 'Wins': 'int', 'Points': 'int'})

    # Add probability columns if they exist
    prob_cols_exist = any('Top 4 Probability' in v for v in standings_data.values()) or \
                      any('Top 2 Probability' in v for v in standings_data.values())

    if prob_cols_exist:
        df['Top 4 Probability'] = df.index.map(lambda x: standings_data[x].get('Top 4 Probability', float('nan')))
        df['Top 2 Probability'] = df.index.map(lambda x: standings_data[x].get('Top 2 Probability', float('nan')))

    # --- <<< MODIFICATION: Use Full Names >>> ---
    df['Team Name'] = df.index.map(lambda x: team_full_names.get(x, x)) # Use full names
    # --- <<< END MODIFICATION >>> ---

    # Sort before adding position
    df.sort_values(by='Points', ascending=False, inplace=True)

    # --- <<< MODIFICATION: Add Position Column >>> ---
    df.insert(0, 'Pos', range(1, len(df) + 1))
    # --- <<< END MODIFICATION >>> ---

    # Define display columns
    display_cols = ['Pos', 'Team Name', 'Matches', 'Wins', 'Points'] # Base columns
    if prob_cols_exist:
        # Conditionally add probability columns if they have non-NaN values
        if not df['Top 4 Probability'].isnull().all():
            display_cols.append('Top 4 Probability')
        if not df['Top 2 Probability'].isnull().all():
            display_cols.append('Top 2 Probability')

    df.reset_index(drop=True, inplace=True)
    return df[display_cols]

# --- Exhaustive Simulation Functions (Renamed) ---
def simulate_season_exhaustive(initial_standings_arg, fixtures_arg):
    """
    Simulates the season exhaustively using provided data.
    Returns a dictionary of probabilities for each team.
    """
    # --- Performance Check ---
    # MAX_EXHAUSTIVE_FIXTURES is defined globally
    if len(fixtures_arg) > EXHAUSTIVE_LIMIT:
        st.error(f"Exhaustive analysis requested for {len(fixtures_arg)} fixtures, which exceeds the limit of {EXHAUSTIVE_LIMIT}. Aborting.")
        return None
    elif len(fixtures_arg) > 15:
         st.warning(f"Running exhaustive simulation for {len(fixtures_arg)} fixtures. This may take some time...")
    # --- End Performance Check ---

    total_matches_per_team = calculate_total_matches_per_team(initial_standings_arg, fixtures_arg)
    if not total_matches_per_team: return None

    scenarios = list(product([0, 1], repeat=len(fixtures_arg)))
    probabilities_dict = {team: {'Top 4 Probability': 0.0, 'Top 2 Probability': 0.0} for team in initial_standings_arg}

    progress_bar = st.progress(0)
    status_text = st.empty()
    total_teams = len(initial_standings_arg)
    start_time = time.time()

    for i, team_priority in enumerate(initial_standings_arg):
        top_4_counts = 0
        top_2_counts = 0
        total_valid_scenarios_for_team = 0

        # Update status for each team being processed
        status_text.text(f"Analyzing scenarios for {team_full_names.get(team_priority, team_priority)} ({i+1}/{total_teams})...")

        for outcome in scenarios: # This is the inner loop, progress within this is hard
            standings_scenario = {t: dict(s) for t, s in initial_standings_arg.items()}
            for match_result, match in zip(outcome, fixtures_arg):
                winner = match[0] if match_result == 1 else match[1]
                loser = match[1] if winner == match[0] else match[0]
                if winner in standings_scenario and loser in standings_scenario:
                    standings_scenario[winner]['Wins'] += 1
                    standings_scenario[winner]['Points'] += 2
                    standings_scenario[winner]['Matches'] += 1
                    standings_scenario[loser]['Matches'] += 1

            if all(standings_scenario[t]['Matches'] == total_matches_per_team[t] for t in standings_scenario):
                total_valid_scenarios_for_team += 1
                sorted_teams = sorted(standings_scenario.items(), key=lambda x: (-x[1]['Points'], x[0] != team_priority, -x[1]['Wins']))
                top_4_teams = sorted_teams[:4]
                top_2_teams = sorted_teams[:2]
                if team_priority in [t[0] for t in top_4_teams]: top_4_counts += 1
                if team_priority in [t[0] for t in top_2_teams]: top_2_counts += 1

        if total_valid_scenarios_for_team > 0:
            probabilities_dict[team_priority]['Top 4 Probability'] = (top_4_counts / total_valid_scenarios_for_team) * 100
            probabilities_dict[team_priority]['Top 2 Probability'] = (top_2_counts / total_valid_scenarios_for_team) * 100

        # Update progress bar after each team is processed
        progress_bar.progress((i + 1) / total_teams)

    end_time = time.time()
    status_text.text(f"Exhaustive simulation completed in {end_time - start_time:.2f} seconds.")
    progress_bar.empty() # Remove progress bar after completion

    return probabilities_dict

def analyze_team_exhaustive(team_name, top_n, initial_standings_arg, fixtures_arg):
    """
    Analyzes prospects for one team using exhaustive simulation based on provided data.
    Returns percentage chance and DataFrame of required outcomes.
    """
    # --- Performance Check ---
    if len(fixtures_arg) > EXHAUSTIVE_LIMIT:
        st.error(f"Exhaustive analysis requested for {len(fixtures_arg)} fixtures, which exceeds the limit of {EXHAUSTIVE_LIMIT}. Aborting.")
        return 0, DataFrame(columns=['Outcome'])
    elif len(fixtures_arg) > 15:
         st.warning(f"Running exhaustive analysis for {len(fixtures_arg)} fixtures. This may take some time...")
    # --- End Performance Check ---

    total_matches_per_team = calculate_total_matches_per_team(initial_standings_arg, fixtures_arg)
    if not total_matches_per_team: return 0, DataFrame(columns=['Outcome'])

    valid_scenarios = 0
    match_wins_count = {tuple(match): {'team_a_wins': 0, 'team_b_wins': 0, 'Outcome': "Result doesn't matter"} for match in fixtures_arg}
    num_fixtures = len(fixtures_arg)
    total_possible_scenarios = 2 ** num_fixtures

    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()
    processed_scenarios = 0

    # Generate all possible outcomes
    scenarios = product([0, 1], repeat=num_fixtures)

    for outcome in scenarios:
        updated_standings = {team: dict(stats) for team, stats in initial_standings_arg.items()}
        outcome_dict = dict(zip(fixtures_arg, outcome))

        for match, result in outcome_dict.items():
            team_a, team_b = match
            winner = team_a if result == 1 else team_b
            loser = team_b if winner == team_a else team_a
            if winner in updated_standings and loser in updated_standings:
                updated_standings[winner]['Wins'] += 1
                updated_standings[winner]['Points'] += 2
                updated_standings[loser]['Matches'] += 1
                updated_standings[winner]['Matches'] += 1

        if all(updated_standings[team]['Matches'] == total_matches_per_team[team] for team in updated_standings):
            sorted_teams = sorted(updated_standings.items(), key=lambda x: (-x[1]['Points'], x[0] != team_name, -x[1]['Wins']))
            if team_name in [team for team, _ in sorted_teams[:top_n]]:
                valid_scenarios += 1
                for match, result in outcome_dict.items():
                    match_key = tuple(match)
                    if match_key in match_wins_count:
                        if result == 1: match_wins_count[match_key]['team_a_wins'] += 1
                        else: match_wins_count[match_key]['team_b_wins'] += 1

        processed_scenarios += 1
        if processed_scenarios % (max(1, total_possible_scenarios // 100)) == 0: # Update progress roughly every 1%
             progress = processed_scenarios / total_possible_scenarios
             progress_bar.progress(progress)
             status_text.text(f"Analyzing scenarios for {team_full_names.get(team_name, team_name)}... {processed_scenarios:,}/{total_possible_scenarios:,} ({progress:.1%})")


    # Final outcome calculation (remains the same)
    if valid_scenarios > 0:
        # Calculate outcomes AFTER iterating through all scenarios
        for match_key, results in match_wins_count.items():
            total_wins_in_success = results['team_a_wins'] + results['team_b_wins']

            if total_wins_in_success == 0:
                # Match never appeared in a successful scenario
                results['Outcome'] = "Result doesn't matter"
            elif results['team_a_wins'] == results['team_b_wins']:
                # Match appeared equally often for both winners in successful scenarios
                results['Outcome'] = "Result doesn't matter"
            elif results['team_a_wins'] > results['team_b_wins']:
                # Team A wins more often in successful scenarios
                results['Outcome'] = f"{match_key[0]} wins"
            else: # results['team_b_wins'] > results['team_a_wins']
                # Team B wins more often in successful scenarios
                results['Outcome'] = f"{match_key[1]} wins"

        # Create DataFrame using the updated 'Outcome' values
        results_df = DataFrame({'Outcome': [results['Outcome'] for results in match_wins_count.values()]},
                               index=[f"{match[0]} vs {match[1]}" for match in match_wins_count.keys()])
        percentage = 100 * valid_scenarios / total_possible_scenarios
    else:
        # If no valid scenarios, return empty DataFrame (or potentially default "doesn't matter" for all?)
        # Current behavior is empty, let's keep it unless specified otherwise.
        results_df = DataFrame(columns=['Outcome'])
        percentage = 0
    # --- END MODIFIED OUTCOME CALCULATION ---

    end_time = time.time()
    status_text.text(f"Exhaustive analysis for {team_full_names.get(team_name, team_name)} completed in {end_time - start_time:.2f} seconds.")
    progress_bar.empty()

    return percentage, results_df

# --- Monte Carlo Simulation Functions (Adapted) ---
def simulate_season_mc(initial_standings_arg, fixtures_arg, num_simulations=NUM_SIMULATIONS_MC):
    """
    Simulates the season using Monte Carlo based on provided data.
    Returns a dictionary of probabilities for each team.
    NOTE: Uses simple Points -> Wins sorting for overall probabilities,
          does NOT apply team-specific priority tie-breaking during this calculation
          for performance reasons and to reflect general chances before specific tie-breaks.
    """
    total_matches_per_team = calculate_total_matches_per_team(initial_standings_arg, fixtures_arg)
    if not total_matches_per_team: return None

    counts = {team: {'top4': 0, 'top2': 0} for team in initial_standings_arg}
    probabilities_dict = {team: {'Top 4 Probability': 0.0, 'Top 2 Probability': 0.0} for team in initial_standings_arg}

    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()

    for i in range(num_simulations):
        standings = {team: dict(stats) for team, stats in initial_standings_arg.items()}
        for match in fixtures_arg:
            outcome = random.choice([0, 1])
            team_a, team_b = match
            winner = team_a if outcome == 1 else team_b
            loser = team_b if outcome == 1 else team_a
            if winner in standings and loser in standings:
                standings[winner]['Wins'] += 1
                standings[winner]['Points'] += 2
                standings[winner]['Matches'] += 1
                standings[loser]['Matches'] += 1

        if all(standings[team]['Matches'] == total_matches_per_team[team] for team in standings):
            # --- Sorting for Overall MC Probability ---
            # Sorts by Points (desc), then Wins (desc). No team-specific priority here.
            sorted_teams = sorted(standings.items(), key=lambda x: (-x[1]['Points'], -x[1]['Wins']))
            # --- End Sorting ---

            top4_teams = [team for team, _ in sorted_teams[:4]]
            top2_teams = [team for team, _ in sorted_teams[:2]]
            for team in initial_standings_arg:
                if team in top4_teams: counts[team]['top4'] += 1
                if team in top2_teams: counts[team]['top2'] += 1

        # Update progress bar periodically
        if (i + 1) % (max(1, num_simulations // 100)) == 0:
            progress = (i + 1) / num_simulations
            progress_bar.progress(progress)
            status_text.text(f"Running Monte Carlo simulation... {i+1:,}/{num_simulations:,} ({progress:.1%})")

    # Calculate final probabilities
    for team in initial_standings_arg:
        probabilities_dict[team]['Top 4 Probability'] = (counts[team]['top4'] / num_simulations) * 100
        probabilities_dict[team]['Top 2 Probability'] = (counts[team]['top2'] / num_simulations) * 100

    end_time = time.time()
    status_text.text(f"Monte Carlo simulation ({num_simulations:,} runs) completed in {end_time - start_time:.2f} seconds.")
    progress_bar.empty()

    return probabilities_dict


def analyze_team_mc(team_name, top_n, initial_standings_arg, fixtures_arg, num_simulations=NUM_SIMULATIONS_MC):
    """
    Analyzes prospects for one team using Monte Carlo based on provided data.
    Returns percentage chance and DataFrame of required outcomes.
    Applies priority sorting for the analyzed team in case of ties on points. # <<< Added comment
    """
    total_matches_per_team = calculate_total_matches_per_team(initial_standings_arg, fixtures_arg)
    if not total_matches_per_team: return 0, DataFrame(columns=['Outcome'])

    valid_scenarios = 0
    match_wins_count = {tuple(match): {'team_a_wins': 0, 'team_b_wins': 0} for match in fixtures_arg}

    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()

    for i in range(num_simulations):
        updated_standings = {team: dict(stats) for team, stats in initial_standings_arg.items()}
        outcome_dict = {}
        for match in fixtures_arg:
            outcome = random.choice([0, 1])
            outcome_dict[tuple(match)] = outcome
            team_a, team_b = match
            winner = team_a if outcome == 1 else team_b
            loser = team_b if outcome == 1 else team_a
            if winner in updated_standings and loser in updated_standings:
                updated_standings[winner]['Wins'] += 1
                updated_standings[winner]['Points'] += 2
                updated_standings[winner]['Matches'] += 1
                updated_standings[loser]['Matches'] += 1

        if all(updated_standings[team]['Matches'] == total_matches_per_team[team] for team in updated_standings):
            # --- <<< MODIFIED SORTING LINE >>> ---
            # Sort by Points (desc), then Priority (asc - team_name gets False=0), then Wins (desc)
            sorted_teams = sorted(updated_standings.items(), key=lambda x: (-x[1]['Points'], x[0] != team_name, -x[1]['Wins']))
            # --- <<< END MODIFIED SORTING LINE >>> ---

            top_n_teams = [team for team, _ in sorted_teams[:top_n]]
            if team_name in top_n_teams:
                valid_scenarios += 1
                for match_key, result in outcome_dict.items():
                    if match_key in match_wins_count:
                        if result == 1: match_wins_count[match_key]['team_a_wins'] += 1
                        else: match_wins_count[match_key]['team_b_wins'] += 1

        # Update progress bar periodically
        if (i + 1) % (max(1, num_simulations // 100)) == 0:
            progress = (i + 1) / num_simulations
            progress_bar.progress(progress)
            status_text.text(f"Analyzing scenarios for {team_full_names.get(team_name, team_name)} (MC)... {i+1:,}/{num_simulations:,} ({progress:.1%})")

    # --- Outcome Calculation (remains the same, uses MC_TOLERANCE) ---
    if valid_scenarios > 0:
        results_data = {}
        for match_key, counts_dict in match_wins_count.items():
            team_a_wins = counts_dict['team_a_wins']
            team_b_wins = counts_dict['team_b_wins']
            total_wins_in_success = team_a_wins + team_b_wins
            outcome_str = "Result doesn't matter" # Default

            if total_wins_in_success == 0:
                outcome_str = "Result doesn't matter"
            else:
                diff = abs(team_a_wins - team_b_wins)
                if (diff / total_wins_in_success) <= MC_TOLERANCE:
                     outcome_str = "Result doesn't matter"
                elif team_a_wins > team_b_wins:
                    outcome_str = f"{match_key[0]} wins"
                else:
                    outcome_str = f"{match_key[1]} wins"
            results_data[match_key] = outcome_str

        results_df = DataFrame({
            'Outcome': [results_data.get(tuple(match), "Result doesn't matter") for match in fixtures_arg]
        }, index=[f"{match[0]} vs {match[1]}" for match in fixtures_arg])
        percentage = 100 * valid_scenarios / num_simulations
    else:
        results_df = DataFrame(columns=['Outcome'])
        percentage = 0
    # --- END Outcome Calculation ---

    end_time = time.time()
    status_text.text(f"Monte Carlo analysis for {team_full_names.get(team_name, team_name)} completed in {end_time - start_time:.2f} seconds.")
    progress_bar.empty()

    return percentage, results_df



# --- Simulate Matches Function (Keep as is) ---
def simulate_matches(results_df, team_name, initial_standings_arg):
    """
    Simulates one specific scenario based on analysis results and initial standings.
    Returns list of match results and the final standings DataFrame.
    """
    if not initial_standings_arg:
         return "Error: Initial standings data missing.", None
    try:
        final_results = {team: {
            'Matches': initial_standings_arg[team]['Matches'], 'Wins': initial_standings_arg[team]['Wins'],
            'Points': initial_standings_arg[team]['Points'], 'priority': 1
        } for team in initial_standings_arg}
        if team_name not in final_results:
             return f"Error: Analyzed team '{team_name}' not found in standings.", None
        final_results[team_name]['priority'] = 0
        match_results_log = []
        for match_str, row in results_df.iterrows():
            try: team_a, team_b = match_str.split(' vs ')
            except ValueError: st.error(f"Could not parse match string: '{match_str}'. Skipping."); continue
            outcome = row['Outcome']
            if "wins" in outcome: winner = team_a if team_a in outcome else team_b; loser = team_b if winner == team_a else team_a
            elif "Result doesn't matter" in outcome: winner, loser = random.choice([(team_a, team_b), (team_b, team_a)])
            else: st.warning(f"Unexpected outcome format for {match_str}: '{outcome}'. Skipping match."); continue
            if winner in final_results and loser in final_results:
                final_results[winner]['Wins'] += 1; final_results[winner]['Matches'] += 1; final_results[winner]['Points'] += 2
                final_results[loser]['Matches'] += 1
                match_results_log.append(f"{winner} defeats {loser}")
            else: st.warning(f"Skipping update for match {match_str} in simulation due to missing team(s).")

        final_results_df = DataFrame.from_dict(final_results, orient='index')
        final_results_df.sort_values(by=['Points', 'priority', 'Wins'], ascending=[False, True, False], inplace=True)
        # --- <<< MODIFICATION 1: Use short names and 'Team' column >>> ---
        final_results_df['Team Name'] = final_results_df.index.map(lambda x: team_full_names.get(x, x))
        # --- <<< END MODIFICATION 1 >>> ---
        # --- <<< MODIFICATION 2: Add Position Column >>> ---
        final_results_df.insert(0, 'Pos', range(1, len(final_results_df) + 1))
        # --- <<< END MODIFICATION 2 >>> ---

        # --- <<< MODIFICATION 2: Update display columns >>> ---
        display_cols = ['Pos', 'Team Name', 'Matches', 'Wins', 'Points']
        # --- <<< END MODIFICATION 2 >>> ---

        # Reset index before returning the styled DataFrame
        final_results_df.reset_index(drop=True, inplace=True)
        return match_results_log, final_results_df[display_cols]

        return match_results_log, final_results_df[display_cols]
    except Exception as e:
        st.error(f"An error occurred during match simulation: {str(e)}")
        import traceback; traceback.print_exc()
        return f"An error occurred during simulation: {str(e)}", None
# --- End Simulate Matches Function ---

# --- Main Streamlit App (Modified) ---

# --- Main Streamlit App (Modified) ---
def main():
    st.set_page_config(layout="wide", page_title="IPL Probability Analyzer")

    # --- <<< MODIFICATION: Refined Theme-Aware CSS >>> ---
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

            /* Base font */
            body, .stApp {
                font-family: 'Inter', sans-serif !important;
            }

            /* Ensure default text uses theme color */
            body, .stApp, p, li, .stMarkdown, .stText, .stAlert, [data-testid="stSidebar"] *, .stDataFrame th, .stDataFrame td, .stRadio label span, .stSelectbox label span {
                color: var(--text-color);
            }

            /* App Background */
            .stApp {
                 background-color: var(--background-color);
            }

            /* Main content area */
            .main .block-container {
                padding: 2rem 3rem 5rem 3rem;
                background-color: color-mix(in srgb, var(--secondary-background-color) 90%, transparent);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                border-radius: 16px;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
                border: 1px solid var(--separator-color);
                margin: 2.5rem auto;
                max-width: 1400px;
            }

            /* Dataframes */
            .stDataFrame {
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                border: 1px solid var(--separator-color);
            }
            .stDataFrame [data-testid="stTable"] thead th {
                background-color: var(--secondary-background-color);
                font-weight: 600;
                color: var(--text-color); /* Theme text for header */
                border-bottom: 2px solid var(--primary-color);
                text-align: center;
                padding: 0.8rem 0.5rem;
            }
            .stDataFrame [data-testid="stTable"] tbody td {
                 border: none;
                 text-align: center;
                 padding: 0.7rem 0.5rem;
                 border-bottom: 1px solid var(--separator-color);
                 /* Text color handled by Streamlit + row style */
            }
             .stDataFrame [data-testid="stTable"] tbody tr:last-child td { border-bottom: none; }
             .stDataFrame [data-testid="stTable"] tbody tr:hover td {
                 background-color: color-mix(in srgb, var(--primary-color) 10%, transparent) !important;
            }

            /* Buttons - Explicit colors */
            .stButton>button {
                border-radius: 8px; padding: 0.7rem 1.3rem; font-weight: 600; border: none;
                background-color: #007bff; color: white; /* Explicit Blue/White */
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15); transition: all 0.25s ease;
                transform: scale(1); cursor: pointer;
            }
            .stButton>button:hover {
                 box-shadow: 0 6px 15px rgba(0, 0, 0, 0.2); transform: scale(1.03);
                 background-color: #0056b3; filter: none;
            }
             .stButton>button:active {
                 transform: scale(0.98); box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                 background-color: #004085; filter: none;
             }
             .stButton>button:disabled {
                 background-color: #6c757d; color: #ced4da; cursor: not-allowed;
                 box-shadow: none; transform: scale(1);
             }

            /* Sidebar */
            [data-testid="stSidebar"] {
                 background-color: var(--secondary-background-color);
                 backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
                 border-right: 1px solid var(--separator-color);
                 box-shadow: 2px 0px 10px rgba(0,0,0,0.05);
            }
             /* Sidebar Widgets */
             .stRadio, .stSelectbox {
                 background-color: var(--background-color); padding: 0.8rem;
                 border-radius: 8px; margin-bottom: 1rem; border: 1px solid var(--separator-color);
             }


            /* --- <<< MODIFICATION: Explicit Theme Text Color for Headers/Caption >>> --- */
            /* Section Headers */
            h1, h2, h3, .stHeadingContainer h1, .stHeadingContainer h2, .stHeadingContainer h3 {
                color: var(--text-color) !important; /* Force theme text color */
                font-weight: 700 !important;
            }
            h1, .stHeadingContainer h1 {
                 border-bottom: 3px solid var(--primary-color);
                 padding-bottom: 0.7rem;
                 margin-bottom: 1.5rem;
            }
            h2, .stHeadingContainer h2 { margin-top: 2.5rem; margin-bottom: 1.2rem; }
            h3, .stHeadingContainer h3 { margin-top: 1.8rem; margin-bottom: 1rem; }

            /* Caption text */
            .stCaption {
                color: var(--text-color) !important; /* Force theme text color */
                opacity: 0.75;
                font-size: 0.9em;
            }
            /* --- <<< END MODIFICATION >>> --- */


            /* Altair Chart Container */
            .stAltairChart {
                 background-color: var(--secondary-background-color); border-radius: 10px;
                 padding: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                 border: 1px solid var(--separator-color);
            }
            /* Altair Chart Text */
            .stAltairChart text {
                 fill: var(--text-color) !important;
                 font-family: 'Inter', sans-serif !important;
            }

            /* Success/Info/Warning boxes */
            .stAlert {
                border-radius: 8px; border-left-width: 5px;
                background-color: var(--secondary-background-color);
                color: var(--text-color); /* Theme text color */
            }
            .stAlert a { color: var(--primary-color); }

        </style>
    """, unsafe_allow_html=True)
    # --- <<< END MODIFICATION >>> ---


    st.title("IPL Qualification Probability Analyzer") # Simplified Title

    # --- Load Data ---
    initial_standings_data, fixtures_data, last_updated, data_source, load_errors = load_data()
    num_fixtures = len(fixtures_data)

    st.caption(f"Data Source: {data_source} | Last Updated: {last_updated} | Remaining Fixtures: {num_fixtures}")
    if load_errors:
        for error in load_errors:
            if "ERROR" in error: st.error(error)
            else: st.warning(error)
    if not initial_standings_data or (not fixtures_data and num_fixtures > 0) :
         st.error("Critical Error: Could not load standings or fixtures data. Cannot proceed.")
         st.stop()
    # --- End Load Data ---

    # --- Sidebar Method Selection ---
    st.sidebar.title("Settings") # Simplified Sidebar Title
    recommended_method = 'Monte Carlo' if num_fixtures > EXHAUSTIVE_LIMIT else 'Exhaustive'
    recommendation_text = f"(Recommended: {recommended_method})"
    if num_fixtures == 0:
        recommended_method = 'None'; recommendation_text = "(Season Complete)"

    method_options = [f'Exhaustive (Exact, Slow >{15} fixtures)', f'Monte Carlo ({NUM_SIMULATIONS_MC:,} sims)'] # Shorter labels
    default_index = 1 if recommended_method == 'Monte Carlo' else 0

    if recommended_method != 'None':
        selected_method_choice = st.sidebar.radio(
            f"Simulation Method {recommendation_text}:",
            method_options, index=default_index, key='sim_method_choice'
        )
        selected_method = 'Exhaustive' if 'Exhaustive' in selected_method_choice else 'Monte Carlo'
        selected_method_display = selected_method # Use simple name for display in headers
    else:
        st.sidebar.info("No remaining fixtures."); selected_method = 'None'; selected_method_display = "None"
    st.sidebar.markdown("---")
    # --- End Sidebar Method Selection ---


    # --- Display Initial Standings ---
    st.subheader("Current Standings")
    df_initial = plot_standings(initial_standings_data)
    if not df_initial.empty:
        # --- <<< MODIFICATION: Use new styling function >>> ---
        st.dataframe(
            df_initial.style.apply(style_team_row, axis=1), # Use style_team_row
            use_container_width=True,
            hide_index=True
        )
        # --- <<< END MODIFICATION >>> ---
    else:
        st.warning("Initial standings data is empty or could not be processed.")
    # --- End Display Initial Standings ---


    # --- Calculate and Display Overall Probabilities ---
    st.subheader(f"Overall Qualification Probabilities") # Simplified Header
    st.caption(f"Method: {selected_method_display}") # Show method used here
    standings_with_probs = None
    cache_key = f'standings_with_probs_{selected_method}'


    # (create_probability_chart function definition should be here - keep as modified before)
    # ... create_probability_chart definition ...
    def create_probability_chart(data_dict, prob_column='Top 4 Probability'):
        if not data_dict:
            return None

        # Prepare data for Altair
        chart_data = []
        for team_key, stats in data_dict.items(): # This loop must be INSIDE the function
            prob = stats.get(prob_column, 0.0) # Default to 0 if missing
            if prob is not None and not isinstance(prob, (int, float)): # Handle potential non-numeric data
                 try: prob = float(prob)
                 except (ValueError, TypeError): prob = 0.0

            # Divide probability by 100
            chart_data.append({
                'Team': team_short_names.get(team_key, team_key),
                'Probability': prob / 100.0 if prob is not None else 0.0,
                # --- <<< MODIFICATION: Use team_styles['bg'] >>> ---
                'Color': team_styles.get(team_key, {'bg': '#808080'})['bg'] # Use bg color from styles
                # --- <<< END MODIFICATION >>> ---
            })

        if not chart_data:
             return None

        df_chart = DataFrame(chart_data)

        # Calculate Height
        chart_height = max(300, len(chart_data) * 35) # Adjust 35px per team as needed

        base = alt.Chart(df_chart).encode(
            x=alt.X('Probability:Q', axis=alt.Axis(format='%', title='Probability', grid=False), scale=alt.Scale(domain=[0, 1])), # Hide grid lines
            y=alt.Y('Team:N', sort='-x', title=None, axis=alt.Axis(ticks=False, domain=False)), # Hide Y-axis ticks/domain
            color=alt.Color('Color:N', scale=None),
            tooltip=[
                alt.Tooltip('Team:N'),
                alt.Tooltip('Probability:Q', format='.4%', title='Probability')
            ]
        ).properties(
            title=f'{prob_column} Chances',
            height=chart_height
        )

        bars = base.mark_bar(cornerRadius=3) # Add slight corner radius

        text = base.mark_text(
            align='left',
            baseline='middle',
            dx=3 # Small nudge right from the bar end
        ).encode(
            text=alt.Text('Probability:Q', format='.4%'),
            color=alt.value('#333333') # Dark grey text for labels
        )

        chart = (bars + text).configure_view(
            strokeWidth=0 # Remove chart border
        )
        return chart

    # Display Cached or Recalculated Probabilities (using chart)
    if cache_key in st.session_state:
         standings_with_probs = st.session_state[cache_key]
         st.caption("(Using cached results)")
         chart = create_probability_chart(standings_with_probs, 'Top 4 Probability')
         if chart: st.altair_chart(chart, use_container_width=True)
         else: st.warning("Could not generate probability chart from cached data.")

    if selected_method != 'None':
        if st.button(f"Calculate Overall Probabilities"): # Simplified button text
            # ... (Calculation logic remains the same) ...
            probabilities = None
            standings_copy = {t: dict(s) for t, s in initial_standings_data.items()}
            fixtures_copy = list(fixtures_data)
            if selected_method == 'Exhaustive': probabilities = simulate_season_exhaustive(standings_copy, fixtures_copy)
            elif selected_method == 'Monte Carlo': probabilities = simulate_season_mc(standings_copy, fixtures_copy, num_simulations=NUM_SIMULATIONS_MC)

            if probabilities:
                standings_with_probs = {t: dict(s) for t, s in initial_standings_data.items()}
                for team, probs in probabilities.items():
                    if team in standings_with_probs: standings_with_probs[team].update(probs)
                st.session_state[cache_key] = standings_with_probs
                st.caption("(Newly Calculated)")
                chart = create_probability_chart(standings_with_probs, 'Top 4 Probability')
                if chart: st.altair_chart(chart, use_container_width=True)
                else: st.warning("Could not generate probability chart from calculated data.")
            else:
                st.warning(f"Could not calculate overall probabilities using {selected_method}.")
                if cache_key in st.session_state: del st.session_state[cache_key]
    elif 'standings_with_probs_None' not in st.session_state:
         st.session_state['standings_with_probs_None'] = initial_standings_data
    # --- End Overall Probabilities ---


    # --- Team Specific Analysis ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Analyze Specific Team")
    # Use FULL names for selection dropdown
    available_teams_full = sorted([name for key, name in team_full_names.items() if key in initial_standings_data])
    if not available_teams_full: st.sidebar.error("No teams available."); st.stop()

    full_team_name = st.sidebar.selectbox("Select Team:", available_teams_full, key="team_select")
    # Map selected full name back to key
    team_key = next((key for key, value in team_full_names.items() if value == full_team_name), None)

    if not team_key: st.sidebar.error("Selected team key not found."); st.stop()

    top_n_choice = st.sidebar.radio("Analyze for:", ["Top 4", "Top 2"], key="top_n_select") # Simplified label
    top_n = 2 if top_n_choice == "Top 2" else 4

    st.subheader(f"Analysis for {full_team_name}")
    st.caption(f"Method: {selected_method_display}")

    analysis_button_clicked = False
    if selected_method != 'None':
        if st.button(f"Analyze {full_team_name}"): # Simplified button text
            # ... (Analysis logic remains the same) ...
            analysis_button_clicked = True
            if 'simulation_results' in st.session_state: del st.session_state['simulation_results']
            if 'simulation_match_outcomes' in st.session_state: del st.session_state['simulation_match_outcomes']
            percentage = 0; team_results_df = DataFrame(columns=['Outcome'])
            standings_copy = {t: dict(s) for t, s in initial_standings_data.items()}
            fixtures_copy = list(fixtures_data)
            try:
                if selected_method == 'Exhaustive': percentage, team_results_df = analyze_team_exhaustive(team_key, top_n, standings_copy, fixtures_copy)
                elif selected_method == 'Monte Carlo': percentage, team_results_df = analyze_team_mc(team_key, top_n, standings_copy, fixtures_copy, num_simulations=NUM_SIMULATIONS_MC)
                st.session_state['results_df'] = team_results_df; st.session_state['analyzed_team_key'] = team_key
                st.session_state['analyzed_percentage'] = percentage; st.session_state['analyzed_method'] = selected_method

                if team_results_df.empty and percentage == 0:
                    st.info(f"{full_team_name} cannot finish in the {top_n_choice} based on this analysis.")
                else:
                    st.success(f"{full_team_name} finishes in the {top_n_choice} in **{percentage:.4f}%** of scenarios.")
                    st.write("Required / Frequent Outcomes:")
                    # --- <<< MODIFICATION: Display Fixture and Outcome >>> ---
                    df_display = team_results_df.reset_index() # Turn index (fixture) into column
                    df_display.rename(columns={'index': 'Fixture'}, inplace=True) # Rename column
                    st.dataframe(
                        df_display[['Fixture', 'Outcome']], # Select both columns
                        use_container_width=True,
                        hide_index=True
                    )
                    # --- <<< END MODIFICATION >>> ---
            except Exception as e:
                 st.error(f"An error occurred during team analysis: {e}"); traceback.print_exc()
                 if 'results_df' in st.session_state: del st.session_state['results_df']
                 if 'analyzed_team_key' in st.session_state: del st.session_state['analyzed_team_key']

    # Display cached team analysis results (logic remains the same, check formatting below)
    cached_analysis_matches = ( not analysis_button_clicked and 'results_df' in st.session_state and
        st.session_state.get('analyzed_team_key') == team_key and st.session_state.get('analyzed_method') == selected_method )

    if cached_analysis_matches:
         st.caption("(Using cached analysis results)")
         percentage = st.session_state.get('analyzed_percentage', 0)
         team_results_df = st.session_state['results_df'] # Get original df with index
         if team_results_df.empty and percentage == 0:
             st.info(f"{full_team_name} cannot finish in the {top_n_choice} based on cached analysis.")
         else:
             st.success(f"{full_team_name} finishes in the {top_n_choice} in **{percentage:.4f}%** of scenarios (cached).")
             st.write("Required / Frequent Outcomes:")
             # --- <<< MODIFICATION: Display Fixture and Outcome (Cached) >>> ---
             df_display = team_results_df.reset_index() # Turn index (fixture) into column
             df_display.rename(columns={'index': 'Fixture'}, inplace=True) # Rename column
             st.dataframe(
                 df_display[['Fixture', 'Outcome']], # Select both columns
                 use_container_width=True,
                 hide_index=True
             ) # --- <<< END MODIFICATION >>> ---

    elif selected_method == 'None': # Season complete logic
         # ... (Season complete logic remains the same) ...
         st.write("Season complete. Analysis based on final standings.")
         final_standings_sorted = sorted(initial_standings_data.items(), key=lambda x: (-x[1]['Points'], -x[1]['Wins']))
         final_pos = -1
         for i, (t_key, _) in enumerate(final_standings_sorted):
              if t_key == team_key: final_pos = i + 1; break
         if final_pos != -1:
              st.write(f"{full_team_name} finished in position **{final_pos}**.")
              if final_pos <= top_n: st.write(f"Achieved {top_n_choice} finish.")
              else: st.write(f"Did not achieve {top_n_choice} finish.")
         else: st.write(f"Could not determine final position for {full_team_name}.")
    # --- End Team Specific Analysis ---


    # --- Simulate Specific Scenario ---
    st.subheader("Simulate One Scenario")
    if selected_method != 'None':
        if st.button("Simulate Scenario"): # Simplified button text
            # ... (Simulation logic remains the same, including checks) ...
            current_team_key = team_key
            if 'results_df' in st.session_state and 'analyzed_team_key' in st.session_state:
                results_df_for_sim = st.session_state['results_df']; analyzed_team_key_from_state = st.session_state['analyzed_team_key']
                analyzed_percentage = st.session_state.get('analyzed_percentage', 0)
                analyzed_team_full_name = team_full_names.get(analyzed_team_key_from_state, analyzed_team_key_from_state)
                current_team_full_name = team_full_names.get(current_team_key, current_team_key)

                if analyzed_team_key_from_state != current_team_key:
                    st.warning(f"Last analysis was for {analyzed_team_full_name}. Please re-run analysis for {current_team_full_name} before simulating.")
                    if 'simulation_results' in st.session_state: del st.session_state['simulation_results']
                    if 'simulation_match_outcomes' in st.session_state: del st.session_state['simulation_match_outcomes']
                elif results_df_for_sim.empty:
                     st.warning(f"Cannot simulate: Analysis found 0% probability ({analyzed_percentage:.4f}%) for {current_team_full_name} to qualify.")
                     if 'simulation_results' in st.session_state: del st.session_state['simulation_results']
                     if 'simulation_match_outcomes' in st.session_state: del st.session_state['simulation_match_outcomes']
                else:
                    sim_status = st.empty(); sim_status.info(f"Simulating scenario for {current_team_full_name}...")
                    try:
                        match_results_log, final_results_df = simulate_matches(results_df_for_sim.copy(), current_team_key, {t: dict(s) for t, s in initial_standings_data.items()})
                        if isinstance(match_results_log, str): st.error(match_results_log)
                        elif final_results_df is not None:
                            st.session_state['simulation_match_outcomes'] = match_results_log; st.session_state['simulation_results'] = final_results_df
                        else: st.error("Simulation failed.")
                        if isinstance(match_results_log, str) or final_results_df is None: # Clear state on error/failure
                             if 'simulation_results' in st.session_state: del st.session_state['simulation_results']
                             if 'simulation_match_outcomes' in st.session_state: del st.session_state['simulation_match_outcomes']
                    except Exception as e:
                         st.error(f"Simulation error: {e}"); traceback.print_exc()
                         if 'simulation_results' in st.session_state: del st.session_state['simulation_results']
                         if 'simulation_match_outcomes' in st.session_state: del st.session_state['simulation_match_outcomes']
                    finally: sim_status.empty()
            else: st.warning("Please run analysis first.")
    else: st.write("Cannot simulate scenario as the season is complete.")

    # --- Display Simulation Results ---
    if 'simulation_results' in st.session_state and 'simulation_match_outcomes' in st.session_state:
        st.markdown("---"); st.subheader("Simulated Scenario Outcome")
        sim_col1, sim_col2 = st.columns([1, 2])
        with sim_col1:
            st.write("**Match Results:**")
            match_outcomes = st.session_state['simulation_match_outcomes']
            st.text_area("Simulated Matches", "\n".join(match_outcomes), height=300, disabled=True)
        with sim_col2:
            st.write("**Final Standings:**")
            final_table_df = st.session_state['simulation_results']
            # --- <<< MODIFICATION: Use new styling function >>> ---
            st.dataframe(
                final_table_df.style.apply(style_team_row, axis=1), # Use style_team_row
                use_container_width=True,
                hide_index=True
            )
            # --- <<< END MODIFICATION >>> ---
        st.markdown("---")
    # --- End Simulation Display ---

if __name__ == "__main__":
    main()
