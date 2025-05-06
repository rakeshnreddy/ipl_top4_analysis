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
from collections import defaultdict # Add this import

# --- File Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_FILE = os.path.join(BASE_DIR, 'analysis_results.json') # Path for precomputed analysis
STANDINGS_FILE = os.path.join(BASE_DIR, 'current_standings.json')
FIXTURES_FILE = os.path.join(BASE_DIR, 'remaining_fixtures.json')
# ---

# --- Configuration ---
EXHAUSTIVE_LIMIT = 23  # Max fixtures for exhaustive simulation
NUM_SIMULATIONS_MC = 1000000 # Number of simulations for Monte Carlo
MC_TOLERANCE = 0.02 # Tolerance for 'Result doesn't matter' in MC (e.g., 2% difference) # <<< ADD THIS
# --- End Configuration ---


# Team colors and full names
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

def style_team_row(row):
    """Applies background color to the entire row based on team full name,
       allowing Streamlit to handle text color for theme compatibility."""
    team_name = row['Team Name'] # Use the 'Team Name' column (full name)
    team_key = full_name_key_mapping.get(team_name) # Use full name mapping
    style_dict = team_styles.get(team_key) # Get dict containing 'bg'

    if style_dict and 'bg' in style_dict:
        # Only set background-color
        style_string = f"background-color: {style_dict['bg']}; color: white;"
        return [style_string] * len(row)
    else:
        # Default style if team not found
        return [''] * len(row)

# --- Fallback Data ---
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

# --- Data Loading Function ---
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

    df['Team Name'] = df.index.map(lambda x: team_full_names.get(x, x)) # Use full names

    # Sort before adding position
    df.sort_values(by='Points', ascending=False, inplace=True)
    df.insert(0, 'Pos', range(1, len(df) + 1))
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
            # Sort by Points (desc), then Priority (asc - team_name gets False=0), then Wins (desc)
            sorted_teams = sorted(updated_standings.items(), key=lambda x: (-x[1]['Points'], x[0] != team_name, -x[1]['Wins']))

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
        final_results_df['Team Name'] = final_results_df.index.map(lambda x: team_full_names.get(x, x))
        final_results_df.insert(0, 'Pos', range(1, len(final_results_df) + 1))
        display_cols = ['Pos', 'Team Name', 'Matches', 'Wins', 'Points']

        # Reset index before returning the styled DataFrame
        final_results_df.reset_index(drop=True, inplace=True)
        return match_results_log, final_results_df[display_cols]

        return match_results_log, final_results_df[display_cols]
    except Exception as e:
        st.error(f"An error occurred during match simulation: {str(e)}")
        import traceback; traceback.print_exc()
        return f"An error occurred during simulation: {str(e)}", None
# --- End Simulate Matches Function ---

def create_probability_chart(data_dict, prob_column='Top 4 Probability'):
    if not data_dict: return None
    chart_data = []
    for team_key, stats in data_dict.items():
        raw = stats.get(prob_column, 0.0)
        try: prob = float(raw)
        except: prob = 0.0
        chart_data.append({
            'Team': team_short_names.get(team_key, team_key),
            'Probability': prob / 100.0,
            'BarColor': team_styles.get(team_key, {'bg':'#808080'})['bg'],
            'ProbText': f"{prob:.4f}%" # Pre-format text string for the text column
        })
    if not chart_data: return None
    df = DataFrame(chart_data)
    height = max(300, len(df) * 35)

    # --- <<< START MODIFICATION: Separate Y Encodings >>> ---
    # Y encoding for Bars (with labels)
    y_encoding_bars = alt.Y('Team:N',
                            sort=alt.SortField(field="Probability", order="descending"),
                            title=None,
                            axis=alt.Axis(ticks=False, domain=False, labels=True)) # Show labels

    # Y encoding for Text Column (NO labels/axis)
    y_encoding_text = alt.Y('Team:N',
                            sort=alt.SortField(field="Probability", order="descending"),
                            title=None,
                            axis=None) # Hide axis and labels
    # --- <<< END MODIFICATION >>> ---

    # Chart 1: Bars ONLY
    bars = alt.Chart(df).mark_bar(cornerRadius=3).encode(
        x=alt.X('Probability:Q', axis=alt.Axis(format='%', title='Probability', grid=False), scale=alt.Scale(domain=[0,1])),
        y=y_encoding_bars, # Use shared Y encoding
        color=alt.Color('BarColor:N', scale=None),
        tooltip=[alt.Tooltip('Team:N', title='Team'), alt.Tooltip('Probability:Q', format='.4%', title='Chance')]
    ).properties(height=height) # Set height on one component

    # Chart 2: Text Column ONLY
    text = alt.Chart(df).mark_text(align='left', baseline='middle').encode(
        y=y_encoding_text,
        text=alt.Text('ProbText:N')
    ).properties(height=height)

    # Concatenate horizontally
    # Add spacing between the bars and the text column
    chart = alt.hconcat(bars, text, spacing=10).resolve_scale(
        y='shared' # IMPORTANT: Ensure Y axes are shared and aligned
    ).properties(
         title=f'{prob_column} Chances', # Overall title for the combined chart
         autosize=alt.AutoSizeParams(type='fit', contains='padding')
    ).configure_view(
        strokeWidth=0 # Remove outer border
    )
    return chart
# --- End create_probability_chart Function ---


def run_exhaustive_analysis_once(initial_standings_arg, fixtures_arg):
    """
    Performs a single exhaustive simulation pass to calculate all metrics.
    Returns a comprehensive dictionary with results for all teams and analyses.
    """
    num_fixtures = len(fixtures_arg)
    team_keys = list(initial_standings_arg.keys())

    # --- Performance Check ---
    if num_fixtures > EXHAUSTIVE_LIMIT:
        st.error(f"Exhaustive analysis requested for {num_fixtures} fixtures, exceeding the limit of {EXHAUSTIVE_LIMIT}. Aborting.")
        return None
    elif num_fixtures > 15:
        st.warning(f"Running full exhaustive analysis for {num_fixtures} fixtures. This may take some time...")
    # --- End Performance Check ---

    total_matches_per_team = calculate_total_matches_per_team(initial_standings_arg, fixtures_arg)
    if not total_matches_per_team: return None

    total_possible_scenarios = 2 ** num_fixtures

    # --- Data Structures for Aggregation ---
    # Overall qualification counts
    overall_counts = {team: {'top4': 0, 'top2': 0} for team in team_keys}
    # Path analysis counts: path_counts[team][k_wins] = {'total': N, 'qualified_top4': N, 'qualified_top2': N}
    path_counts = defaultdict(lambda: defaultdict(lambda: {'total': 0, 'qualified_top4': 0, 'qualified_top2': 0}))
    # Required outcome counts: req_outcome_counts[team][target_n][match_tuple] = {'team_a_wins': N, 'team_b_wins': N}
    req_outcome_counts = defaultdict(lambda: {
        4: defaultdict(lambda: {'team_a_wins': 0, 'team_b_wins': 0}),
        2: defaultdict(lambda: {'team_a_wins': 0, 'team_b_wins': 0})
    })
    total_valid_scenarios = 0
    # --- End Data Structures ---

    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()
    processed_scenarios = 0

    # --- Single Pass Simulation Loop ---
    for i, outcome_tuple in enumerate(product([0, 1], repeat=num_fixtures)):
        standings_scenario = {t: dict(s) for t, s in initial_standings_arg.items()}
        team_wins_in_scenario = {team: 0 for team in team_keys}
        match_outcomes_this_scenario = {} # Store match results for this scenario

        # Apply results for this specific scenario
        for match_idx, result in enumerate(outcome_tuple):
            match = fixtures_arg[match_idx]
            match_key = tuple(match)
            match_outcomes_this_scenario[match_key] = result # Store 0 or 1
            team_a, team_b = match
            winner = team_a if result == 1 else team_b
            loser = team_b if winner == team_a else team_a
            if winner in standings_scenario and loser in standings_scenario:
                standings_scenario[winner]['Wins'] += 1; standings_scenario[winner]['Points'] += 2
                standings_scenario[winner]['Matches'] += 1; standings_scenario[loser]['Matches'] += 1
                if winner in team_wins_in_scenario: team_wins_in_scenario[winner] += 1

        # Check if the scenario is valid
        if all(standings_scenario[team]['Matches'] == total_matches_per_team.get(team, -1) for team in standings_scenario):
            total_valid_scenarios += 1

            # Analyze results for EACH team within this single scenario
            for current_team_key in team_keys:
                k_wins = team_wins_in_scenario[current_team_key]
                path_counts[current_team_key][k_wins]['total'] += 1

                # Sort with priority for the current_team_key
                sorted_teams_prio = sorted(standings_scenario.items(), key=lambda x: (-x[1]['Points'], x[0] != current_team_key, -x[1]['Wins']))

                # Check Top 4 Qualification
                top_4_teams_keys = {t[0] for t in sorted_teams_prio[:4]}
                qualified_top4 = current_team_key in top_4_teams_keys
                if qualified_top4:
                    overall_counts[current_team_key]['top4'] += 1
                    path_counts[current_team_key][k_wins]['qualified_top4'] += 1
                    # Increment required outcome counts for Top 4
                    for match_key, result in match_outcomes_this_scenario.items():
                        if result == 1: # Team A won
                            req_outcome_counts[current_team_key][4][match_key]['team_a_wins'] += 1
                        else: # Team B won
                            req_outcome_counts[current_team_key][4][match_key]['team_b_wins'] += 1

                # Check Top 2 Qualification
                top_2_teams_keys = {t[0] for t in sorted_teams_prio[:2]}
                qualified_top2 = current_team_key in top_2_teams_keys
                if qualified_top2:
                    overall_counts[current_team_key]['top2'] += 1
                    path_counts[current_team_key][k_wins]['qualified_top2'] += 1
                     # Increment required outcome counts for Top 2
                    for match_key, result in match_outcomes_this_scenario.items():
                        if result == 1: # Team A won
                            req_outcome_counts[current_team_key][2][match_key]['team_a_wins'] += 1
                        else: # Team B won
                            req_outcome_counts[current_team_key][2][match_key]['team_b_wins'] += 1

        # Update progress
        processed_scenarios += 1
        if (i + 1) % (max(1, total_possible_scenarios // 100)) == 0:
             progress = (i + 1) / total_possible_scenarios
             try:
                 progress_bar.progress(progress)
                 status_text.text(f"Running full exhaustive analysis... {processed_scenarios:,}/{total_possible_scenarios:,} ({progress:.1%})")
             except Exception as pb_e:
                 st.warning(f"Progress bar update error: {pb_e}")
    # --- End Single Pass Loop ---

    # --- Post-Processing ---
    final_results = {
        'overall_probabilities': {},
        'team_analysis': {4: {}, 2: {}}, # Store required outcomes DFs
        'qualification_path': {4: {}, 2: {}} # Store possible/guaranteed wins
    }

    if total_valid_scenarios == 0:
        st.error("No valid scenarios found during exhaustive analysis. Cannot calculate results.")
        return None # Or return empty structure

    # 1. Calculate Overall Probabilities
    for team in team_keys:
        final_results['overall_probabilities'][team] = {
            'Top 4 Probability': (overall_counts[team]['top4'] / total_valid_scenarios) * 100 if total_valid_scenarios > 0 else 0,
            'Top 2 Probability': (overall_counts[team]['top2'] / total_valid_scenarios) * 100 if total_valid_scenarios > 0 else 0
        }

    # 2. Calculate Required Outcomes (Team Analysis)
    for team in team_keys:
        for target_n in [4, 2]:
            team_qualified_count = overall_counts[team]['top4'] if target_n == 4 else overall_counts[team]['top2']
            outcome_details = {}
            if team_qualified_count > 0:
                for match_key in fixtures_arg: # Iterate through all fixtures
                    match_key_tuple = tuple(match_key)
                    counts_dict = req_outcome_counts[team][target_n][match_key_tuple]
                    team_a_wins = counts_dict['team_a_wins']
                    team_b_wins = counts_dict['team_b_wins']
                    total_wins_in_success = team_a_wins + team_b_wins
                    outcome_str = "Result doesn't matter" # Default

                    if total_wins_in_success > 0: # Only consider if match occurred in successful scenarios
                        # Using simple majority for exhaustive 'required'
                        if team_a_wins == team_qualified_count: outcome_str = f"{match_key[0]} wins"
                        elif team_b_wins == team_qualified_count: outcome_str = f"{match_key[1]} wins"
                        elif team_a_wins > team_b_wins: outcome_str = f"{match_key[0]} wins" # Frequent
                        elif team_b_wins > team_a_wins: outcome_str = f"{match_key[1]} wins" # Frequent
                        # else: remains "Result doesn't matter"

                    outcome_details[f"{match_key[0]} vs {match_key[1]}"] = outcome_str

                results_df = DataFrame({'Outcome': outcome_details})
                percentage = (team_qualified_count / total_valid_scenarios) * 100 if total_valid_scenarios > 0 else 0
            else:
                results_df = DataFrame(columns=['Outcome'])
                percentage = 0

            # Convert DataFrame to dictionary before storing
            final_results['team_analysis'][target_n][team] = {
                'percentage': percentage,
                'results_df': results_df.to_dict(orient='index') # Convert to dict
            }
    # 3. Calculate Qualification Path
    num_target_matches_map = {team: sum(1 for m in fixtures_arg if team in m) for team in team_keys}
    for team in team_keys:
        for target_n in [4, 2]:
            possible_wins_set = set()
            min_wins_guaranteed = None
            num_team_matches = num_target_matches_map[team]

            # Find possible wins
            for k in range(num_team_matches + 1):
                qual_count = path_counts[team][k][f'qualified_top{target_n}']
                if qual_count > 0:
                    possible_wins_set.add(k)

            min_wins_possible = min(possible_wins_set) if possible_wins_set else None

            # Find guaranteed wins (iterating UPWARDS now)
            for k in range(num_team_matches + 1):
                total_for_k = path_counts[team][k]['total']
                qual_for_k = path_counts[team][k][f'qualified_top{target_n}']
                if total_for_k > 0 and qual_for_k == total_for_k:
                    min_wins_guaranteed = k
                    break # Found the minimum guarantee

            final_results['qualification_path'][target_n][team] = {
                'possible': min_wins_possible,
                'guaranteed': min_wins_guaranteed,
                'target_matches': num_team_matches
            }
    # --- End Post-Processing ---

    end_time = time.time()
    try:
        status_text.text(f"Full exhaustive analysis completed in {end_time - start_time:.2f} seconds.")
        progress_bar.empty()
    except Exception as pb_e:
        st.warning(f"Final progress bar update error: {pb_e}")

    return final_results



# --- Main Streamlit App (Modified) ---
def main():
    st.set_page_config(layout="wide", page_title="IPL Probability Analyzer")
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            /* --- Base & Theme Variables --- */
            :root {
                --font-family-sans-serif: 'Inter', sans-serif;
                --border-radius-lg: 16px;
                --border-radius-md: 10px;
                --border-radius-sm: 8px;
                --box-shadow-light: 0 4px 12px rgba(0, 0, 0, 0.08);
                --box-shadow-medium: 0 6px 20px rgba(0, 0, 0, 0.1);
                --transition-fast: all 0.2s ease-in-out;
                --transition-medium: all 0.3s ease-in-out;
            }

            /* --- Base Font --- */
            /* Let Streamlit handle base body/app background and text color */
            body, .stApp {
                font-family: var(--font-family-sans-serif) !important;
            }

            /* --- Main Layout --- */
            .stApp > header { display: block; } /* Ensure header is visible */
            .main .block-container {
                padding: 2rem 3rem 4rem 3rem;
                background-color: var(--secondary-background-color); /* Use secondary for contrast */
                border-radius: var(--border-radius-lg);
                box-shadow: var(--box-shadow-medium);
                border: 1px solid var(--separator-color);
                margin: 2rem auto;
                max-width: 1400px;
            }

            /* --- Sidebar --- */
            [data-testid="stSidebar"] {
                 background-color: var(--secondary-background-color);
                 border-right: 1px solid var(--separator-color);
                 box-shadow: 2px 0px 10px rgba(0,0,0,0.05);
                 padding-top: 1rem;
            }
            /* Ensure sidebar text uses theme color */
            [data-testid="stSidebar"] * {
                 color: var(--text-color) !important; /* Keep important here for specificity */
            }
            [data-testid="stSidebar"] .stRadio,
            [data-testid="stSidebar"] .stSelectbox {
                 background-color: var(--background-color); padding: 0.8rem;
                 border-radius: var(--border-radius-sm); margin-bottom: 1rem;
                 border: 1px solid var(--separator-color);
            }


            /* --- Headers & Text (Targeting for Theme Color) --- */
            /* Keep !important on headers/captions as they seem needed */
            h1, h2, h3,
            [data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3,
            .stHeadingContainer h1, .stHeadingContainer h2, .stHeadingContainer h3,
            div[data-testid="stMarkdownContainer"] h1, div[data-testid="stMarkdownContainer"] h2, div[data-testid="stMarkdownContainer"] h3
            {
                color: var(--text-color) !important;
                font-weight: 700 !important;
            }
            h1, [data-testid="stHeading"] h1, .stHeadingContainer h1, div[data-testid="stMarkdownContainer"] h1 {
                 border-bottom: 3px solid var(--primary-color); padding-bottom: 0.8rem;
                 margin-bottom: 2rem; font-size: 2.2em;
            }
            h2, [data-testid="stHeading"] h2, .stHeadingContainer h2, div[data-testid="stMarkdownContainer"] h2 {
                 margin-top: 3rem; margin-bottom: 1.5rem; font-size: 1.6em;
                 border-bottom: 1px solid var(--separator-color); padding-bottom: 0.5rem;
            }
            h3, [data-testid="stHeading"] h3, .stHeadingContainer h3, div[data-testid="stMarkdownContainer"] h3 {
                 margin-top: 2rem; margin-bottom: 1rem; font-size: 1.3em;
                 font-weight: 600 !important;
            }
            .stCaption, [data-testid="stCaptionContainer"] {
                color: var(--text-color) !important;
                opacity: 0.7; font-size: 0.9em;
                margin-top: -0.8rem; margin-bottom: 1rem;
            }
            /* Default paragraph text - Should inherit from body/stApp now */
            p, .stMarkdown p, .stText {
                 line-height: 1.6;
                 /* color: var(--text-color); REMOVED - Let it inherit */
            }

            /* --- Buttons (Keep Explicit Colors) --- */
            /* ... (Keep the explicit blue/white button CSS) ... */
            .stButton>button { border-radius: var(--border-radius-sm); padding: 0.75rem 1.5rem; font-weight: 600; border: none; background-image: linear-gradient(to right, #0061ff, #007bff, #0095ff); background-size: 200% auto; color: white; box-shadow: 0 4px 10px rgba(0, 123, 255, 0.2); transition: var(--transition-medium); transform: scale(1); cursor: pointer; }
            .stButton>button:hover { background-position: right center; box-shadow: 0 7px 18px rgba(0, 123, 255, 0.3); transform: scale(1.03); }
            .stButton>button:active { transform: scale(0.98); box-shadow: 0 2px 5px rgba(0, 123, 255, 0.2); }
            .stButton>button:disabled { background-image: none; background-color: #adb5bd; color: #dee2e6; cursor: not-allowed; box-shadow: none; transform: scale(1); opacity: 0.7; }


            /* --- Dataframes --- */
            /* ... (Keep DataFrame CSS as is) ... */
            .stDataFrame { border-radius: var(--border-radius-md); overflow: hidden; box-shadow: var(--box-shadow-light); border: 1px solid var(--separator-color); }
            .stDataFrame [data-testid="stTable"] thead th { background-color: var(--secondary-background-color); font-weight: 600; color: var(--text-color); border-bottom: 2px solid var(--primary-color); text-align: center; padding: 0.8rem 0.5rem; }
            .stDataFrame [data-testid="stTable"] tbody td { border: none; text-align: center; padding: 0.75rem 0.5rem; border-bottom: 1px solid var(--separator-color); font-weight: 500; }
            .stDataFrame [data-testid="stTable"] tbody tr:last-child td { border-bottom: none; }
            .stDataFrame [data-testid="stTable"] tbody tr:hover td { background-color: color-mix(in srgb, var(--primary-color) 10%, transparent) !important; }
            .stDataFrame [data-testid="stTable"] tbody td:first-child { font-weight: 700; color: var(--primary-color); }


            /* --- Altair Chart --- */
            .stAltairChart { /* Container styles */ }
            .stAltairChart text { font-family: var(--font-family-sans-serif) !important; }
            .stAltairChart .hconcat_0 .axis text { fill: var(--text-color) !important; opacity: 0.8; font-size: 11px; }
            .stAltairChart .title text { fill: var(--text-color) !important; font-weight: 600 !important; font-size: 14px !important; }
            .stAltairChart .hconcat_1 g.mark-text text { fill: var(--text-color) !important; font-size: 11px; }
        </style>
    """, unsafe_allow_html=True)

    analysis = None # Initialize analysis variable
    try:
        with open(ANALYSIS_FILE, 'r') as f:
            analysis = json.load(f)
        #st.caption(f"🔍 Loaded cached analysis from {ANALYSIS_FILE}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        st.warning(f"Could not load cached analysis file ({e}). Running analysis now...")
        # Need to load data first to run analysis
        standings_data_init, fixtures_data_init, _, _, load_errors_init = load_data()
        if not load_errors_init or not any("CRITICAL" in err for err in load_errors_init):
            if fixtures_data_init is not None and len(fixtures_data_init) <= EXHAUSTIVE_LIMIT:
                analysis = run_exhaustive_analysis_once(standings_data_init, fixtures_data_init)
                if analysis:
                    try:
                        with open(ANALYSIS_FILE, 'w') as f:
                            json.dump(analysis, f, indent=4)
                        st.caption("⚙️ Computed and cached new analysis results.")
                    except IOError as write_e:
                        st.error(f"Failed to write cache file {ANALYSIS_FILE}: {write_e}")
                else:
                    st.error("Exhaustive analysis failed during initial computation.")
            elif fixtures_data_init is not None: # Exceeds limit
                 st.warning(f"Number of fixtures ({len(fixtures_data_init)}) exceeds exhaustive limit ({EXHAUSTIVE_LIMIT}). Cannot precompute. Exhaustive mode will be unavailable.")
            else: # Fixtures failed to load
                 st.error("Could not load fixtures data. Cannot precompute exhaustive analysis.")
        else:
            st.error("Critical error loading initial data. Cannot precompute exhaustive analysis.")
    except Exception as e:
         st.error(f"An unexpected error occurred loading or computing analysis: {e}")
         traceback.print_exc() # Print full traceback for unexpected errors

    # If analysis is still None after trying to load/compute, stop or handle error
    if analysis is None:
        st.error("Failed to load or compute exhaustive analysis data. Exhaustive method unavailable.")
        # Optionally, force method to Monte Carlo if possible, or stop
        # For now, we'll let it continue but Exhaustive sections will show errors/info

    st.title("IPL Qualification Probability Analyzer")

    # --- Load Data ---
    initial_standings_data, fixtures_data, last_updated, data_source, load_errors = load_data()
    num_fixtures = len(fixtures_data)

    # Format the last updated time for better readability
    formatted_update_time = "N/A"
    if last_updated and last_updated != "N/A":
        try:
            # Parse ISO string, handling the 'Z' for UTC timezone
            dt_obj = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            # Format like: May 03, 2025 10:29 UTC
            formatted_update_time = dt_obj.strftime("%b %d, %Y %H:%M UTC")
        except ValueError:
            # If parsing fails for any reason, just use the original string
            formatted_update_time = last_updated

    # Construct the simplified caption
    st.caption(f"Data Updated: {formatted_update_time} | Fixtures Remaining: {num_fixtures}")
    if load_errors:
        for error in load_errors:
            if "ERROR" in error: st.error(error)
            else: st.warning(error)
    if not initial_standings_data or (not fixtures_data and num_fixtures > 0) :
         st.error("Critical Error: Could not load standings or fixtures data. Cannot proceed.")
         st.stop()
    # --- End Load Data ---
    
    # --- Sidebar (Simplified) ---
    # st.sidebar.title("IPL Analyzer") # Simplified title
    # st.sidebar.markdown("---")
    # st.sidebar.write("Analysis uses precomputed data.")
    # st.sidebar.write("Data is updated periodically via automation.")
    # --- Sidebar Method Selection ---
    
    # st.sidebar.title("Settings") # Simplified Sidebar Title
    # recommended_method = 'Monte Carlo' if num_fixtures > EXHAUSTIVE_LIMIT else 'Exhaustive'
    # recommendation_text = f"(Recommended: {recommended_method})"
    # if num_fixtures == 0:
    #     recommended_method = 'None'; recommendation_text = "(Season Complete)"

    # method_options = []
    # if analysis is not None or num_fixtures <= EXHAUSTIVE_LIMIT: # Only offer Exhaustive if precomputed or computable
    #      method_options.append(f'Exhaustive (Precomputed/Exact)')
    # method_options.append(f'Monte Carlo ({NUM_SIMULATIONS_MC:,} sims)')

    # recommended_method = 'Monte Carlo' if num_fixtures > EXHAUSTIVE_LIMIT or analysis is None else 'Exhaustive'
    # recommendation_text = f"(Recommended: {recommended_method})" if recommended_method != 'None' else "(Season Complete)"
    # if num_fixtures == 0: recommended_method = 'None'

    # default_index = 0 # Default to first option
    # if recommended_method == 'Monte Carlo' and len(method_options) > 1:
    #     default_index = 1 # Index of Monte Carlo if Exhaustive is also an option
    # elif recommended_method == 'Monte Carlo':
    #     default_index = 0 # Index of Monte Carlo if it's the only option

    # if recommended_method != 'None':
    #     if not method_options:
    #          st.sidebar.error("No analysis methods available.")
    #          st.stop()
    #     selected_method_choice = st.sidebar.radio(
    #         f"Simulation Method {recommendation_text}:",
    #         method_options, index=default_index, key='sim_method_choice'
    #     )
    #     selected_method = 'Exhaustive' if 'Exhaustive' in selected_method_choice else 'Monte Carlo'
    #     selected_method_display = selected_method
    # else:
    #     st.sidebar.info("No remaining fixtures."); selected_method = 'None'; selected_method_display = "None"
    
    # st.sidebar.markdown("---") # Separator
    # st.sidebar.subheader("Analysis Target") # New subheader
    # # --- End Sidebar Method Selection ---
    # top_n_choice = st.sidebar.radio("Analyze for:", ["Top 4", "Top 2"], key="top_n_select")
    # top_n = 2 if top_n_choice == "Top 2" else 4
    # st.sidebar.markdown("---")
    # # --- End Sidebar Team/Target Selection ---
    # --- Display Initial Standings ---
    st.subheader("Current Standings")
    df_initial = plot_standings(initial_standings_data)
    if not df_initial.empty:
        st.dataframe(
            df_initial.style.apply(style_team_row, axis=1), # Use style_team_row
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("Initial standings data is empty or could not be processed.")
    # --- End Display Initial Standings ---
    # --- Determine Method to Display (Prioritize Exhaustive) ---
    analysis_method_used = "N/A"
    analysis_data = None # Will hold the actual results dict

    if analysis and "metadata" in analysis and "analysis_data" in analysis:
        analysis_method_used = analysis["metadata"].get("method_used", "Unknown")
        analysis_data = analysis["analysis_data"] # Get the main results dict
        if not analysis_data: # Check if analysis_data itself is null/empty
             st.error("Precomputed analysis data is empty or invalid.")
             analysis_method_used = "Error" # Mark as error state
    elif analysis:
        st.error("Precomputed analysis file has incorrect structure (missing metadata or analysis_data).")
        analysis_method_used = "Error"
    else:
        # analysis is None (loading/computation failed earlier)
        st.error("Precomputed analysis data is unavailable.")
        analysis_method_used = "Unavailable"

    # --- Display Overall Probabilities (Side-by-Side) ---
    st.subheader(f"Overall Qualification Probabilities")
    st.caption(f"Method Used: {analysis_method_used}") # Display the method from metadata

    # Check if analysis_data and the specific key exist
    if analysis_data and "overall_probabilities" in analysis_data:
        overall_probs_source = analysis_data["overall_probabilities"]
        col1, col2 = st.columns(2)
        # Prepare data structure for charts
        display_data_for_chart = {t: dict(initial_standings_data.get(t, {})) for t in overall_probs_source}
        for team, probs in overall_probs_source.items():
            if team in display_data_for_chart:
                display_data_for_chart[team].update(probs)
        
        ## # --- ADD DEBUG PRINT ---
        ## st.write("DEBUG: Data for Charts:")
        ## st.json(display_data_for_chart)
        ## # --- END DEBUG PRINT ---
        with col1:
            st.markdown("##### Top 4 Chances")
            chart_top4 = create_probability_chart(display_data_for_chart, 'Top 4 Probability')
            if chart_top4: st.altair_chart(chart_top4, use_container_width=True)
            else: st.warning("Could not generate Top 4 chart.")
        with col2:
            st.markdown("##### Top 2 Chances")
            chart_top2 = create_probability_chart(display_data_for_chart, 'Top 2 Probability')
            if chart_top2: st.altair_chart(chart_top2, use_container_width=True)
            else: st.warning("Could not generate Top 2 chart.")
    else:
        st.warning(f"Overall probability data not available (Method: {analysis_method_used}).")
    # --- End Overall Probabilities ---
    
    # --- Team Selection and Target (Main Area) ---
    st.divider()
    st.subheader("Detailed Team Analysis")

    col_team, col_target = st.columns([3, 1]) # Adjust ratios as needed

    with col_team:
        available_teams_full = sorted([name for key, name in team_full_names.items() if key in initial_standings_data])
        if not available_teams_full: st.error("No teams available."); st.stop()
        full_team_name = st.selectbox("Select Team:", available_teams_full, key="team_select_main", label_visibility="collapsed") # Hide label
        team_key = next((key for key, value in team_full_names.items() if value == full_team_name), None)
        if not team_key: st.error("Selected team key not found."); st.stop()

    with col_target:
        top_n_choice = st.radio("Analyze for:", ["Top 4", "Top 2"], key="top_n_select_main", horizontal=True, label_visibility="collapsed") # Horizontal layout
        top_n = 2 if top_n_choice == "Top 2" else 4
    # --- End Team Selection ---

    # --- Display Team Specific Analysis ---
    # Header is now part of the selection area
    st.caption(f"Displaying {analysis_method_used} results for {full_team_name} ({top_n_choice})")

    # Check if analysis_data and the specific key exist
    if analysis_data and "team_analysis" in analysis_data:
        try:
            # Access data via analysis_data
            team_data = analysis_data["team_analysis"][str(top_n)][team_key]
            percentage = team_data['percentage']
            team_results_df = DataFrame.from_dict(team_data['results_df'], orient='index')

            if team_results_df.empty and percentage == 0:
                st.info(f"{full_team_name} cannot finish in the {top_n_choice} based on {analysis_method_used} analysis.")
            else:
                st.success(f"{full_team_name} finishes in the {top_n_choice} in **{percentage:.4f}%** of scenarios ({analysis_method_used}).")
                st.write("Required / Frequent Outcomes:")
                df_display = team_results_df.reset_index().rename(columns={'index': 'Fixture'})
                st.dataframe(df_display[['Fixture', 'Outcome']], use_container_width=True, hide_index=True)
        except KeyError:
            st.error(f"Could not retrieve {analysis_method_used} analysis data for {full_team_name} (Top {top_n}).")
        except Exception as e:
            st.error(f"Error displaying {analysis_method_used} team analysis: {e}")
    else:
        st.warning("Team-specific analysis data not available.")
    # --- End Team Specific Analysis ---

    
    # --- Display Qualification Path ---
    st.subheader(f"Qualification Path for {full_team_name} (Top {top_n})")
    st.caption("Minimum wins analysis (Exhaustive method only).")
    path_data = None


    # Explicitly check if method was Exhaustive AND data exists
    if analysis and analysis_method_used == "Exhaustive" and analysis_data and "qualification_path" in analysis_data:
        try:
            path_data = analysis_data["qualification_path"][str(top_n)][team_key]
            possible_wins = path_data.get('possible')
            guaranteed_wins = path_data.get('guaranteed')
            target_matches = path_data.get('target_matches', 'N/A')

            ##  # --- <<< ADD DEBUG PRINTS >>> ---
            ##  st.write(f"DEBUG: possible_wins = {possible_wins} (type: {type(possible_wins)})")
            ##  st.write(f"DEBUG: guaranteed_wins = {guaranteed_wins} (type: {type(guaranteed_wins)})")
            ##  # --- <<< END DEBUG PRINTS >>> ---

            st.write(f"**Remaining Matches for {full_team_name}:** {target_matches}")

            # Now check the conditions
            if isinstance(possible_wins, int): 
                st.success(f"**Possible Qualification:** Win **{possible_wins}** match(es) (with favorable results).")
            elif possible_wins is None: st.error(f"**Possible Qualification:** Cannot qualify.")
            else: st.warning(f"**Possible Qualification:** Analysis result: {possible_wins}")
            if isinstance(guaranteed_wins, int):
                st.success(f"**Guaranteed Qualification:** Win **{guaranteed_wins}** match(es) (irrespective of other results).")
            elif guaranteed_wins is None and possible_wins is not None: # Check possible_wins to avoid repeating error
                 st.info(f"**Guaranteed Qualification:** Cannot guarantee qualification based solely on own wins.")
            elif guaranteed_wins is None and possible_wins is None:
                 pass # Error already shown by possible_wins block
            else: # Handle unexpected non-int, non-None types if necessary
                st.warning(f"**Guaranteed Qualification:** Analysis result: {guaranteed_wins}")
            # --- <<< END ADDED BLOCK >>> ---
      
        except KeyError:
            st.error(f"Could not retrieve Exhaustive path data for {full_team_name} (Top {top_n}). Key missing.")
        except Exception as e:
            st.error(f"Error displaying Exhaustive path analysis: {e}")
    else:
        # Explain why it's not shown
        if analysis_method_used == "Monte Carlo (Precomputed)":
             st.info("Qualification Path analysis is only available when Exhaustive method is used.")
        elif analysis_method_used == "Exhaustive (Precomputed)":
             st.warning("Exhaustive qualification path data not found in precomputed results.")
        else: # Unavailable or Error
             st.info("Qualification Path analysis requires precomputed Exhaustive results.")
    st.markdown("---")
    # --- End Qualification Path ---

    # --- Simulate Specific Scenario ---
    st.subheader("Simulate One Scenario")
    results_df_for_sim = None
    source_method_for_sim = "N/A"

    # Check if analysis_data and the specific key exist
    if analysis_data and "team_analysis" in analysis_data:
         try:
             # Access data via analysis_data
             sim_data = analysis_data["team_analysis"][str(top_n)][team_key]
             results_df_for_sim = DataFrame.from_dict(sim_data['results_df'], orient='index')
             source_method_for_sim = analysis_method_used # Use the determined method
         except KeyError:
             st.warning("Could not find results for simulation.")
    else:
         st.warning(f"Analysis data unavailable for simulation (Method: {analysis_method_used}).")

    if results_df_for_sim is not None:
        st.caption(f"(Using results from: {source_method_for_sim})")
        if st.button("Simulate Scenario"):
            percentage_for_sim = 0
            if analysis_data and "team_analysis" in analysis_data: # Check again
                 try: percentage_for_sim = analysis_data["team_analysis"][str(top_n)][team_key]['percentage']
                 except KeyError: pass

            if results_df_for_sim.empty:
                 st.warning(f"Cannot simulate: Analysis found 0% probability ({percentage_for_sim:.4f}%) for {full_team_name} to qualify using {source_method_for_sim} results.")
                 if 'simulation_results' in st.session_state: del st.session_state['simulation_results']
                 if 'simulation_match_outcomes' in st.session_state: del st.session_state['simulation_match_outcomes']
            else:
                # ... (Simulation execution logic remains the same) ...
                sim_status = st.empty(); sim_status.info(f"Simulating scenario for {full_team_name}...")
                try:
                    match_results_log, final_results_df = simulate_matches(results_df_for_sim.copy(), team_key, {t: dict(s) for t, s in initial_standings_data.items()})
                    if isinstance(match_results_log, str): st.error(match_results_log)
                    elif final_results_df is not None: st.session_state['simulation_match_outcomes'] = match_results_log; st.session_state['simulation_results'] = final_results_df
                    else: st.error("Simulation failed.")
                    if isinstance(match_results_log, str) or final_results_df is None:
                         if 'simulation_results' in st.session_state: del st.session_state['simulation_results']
                         if 'simulation_match_outcomes' in st.session_state: del st.session_state['simulation_match_outcomes']
                except Exception as e: st.error(f"Simulation error: {e}"); traceback.print_exc()
                finally: sim_status.empty()

    # --- Display Simulation Results (remains the same) ---
    if 'simulation_results' in st.session_state and 'simulation_match_outcomes' in st.session_state:
        # ... (Display logic is unchanged) ...
        st.markdown("---"); st.subheader("Simulated Scenario Outcome")
        sim_col1, sim_col2 = st.columns([1, 2])
        with sim_col1:
            st.write("**Match Results:**")
            match_outcomes = st.session_state['simulation_match_outcomes']
            st.text_area("Simulated Matches", "\n".join(match_outcomes), height=300, disabled=True)
        with sim_col2:
            st.write("**Final Standings:**")
            final_table_df = st.session_state['simulation_results']
            st.dataframe(
                final_table_df.style.apply(style_team_row, axis=1),
                use_container_width=True,
                hide_index=True
            )
        st.markdown("---")
    # --- End Simulation Display ---

if __name__ == "__main__":
    main()
