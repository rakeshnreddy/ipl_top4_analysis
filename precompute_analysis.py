import json
import os
import time
from datetime import datetime
from pandas import DataFrame # Make sure DataFrame is imported

# Import necessary functions from your main app file
from ipl_analysis_app import (
    load_data,
    run_exhaustive_analysis_once, # Keep this for exhaustive part
    simulate_season_mc,           # For MC overall
    analyze_team_mc,              # For MC team-specific
    # EXHAUSTIVE_LIMIT,           # We'll use a hardcoded threshold here
    NUM_SIMULATIONS_MC            # Use the MC simulation count
)

# Define file paths (relative to this script's location)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_FILE = os.path.join(BASE_DIR, 'analysis_results.json')
EXHAUSTIVE_THRESHOLD = 22 # Run exhaustive if num_fixtures < this value (i.e., <= 21)

def precompute_analysis():
    """Runs EITHER exhaustive OR Monte Carlo analysis based on fixture count and saves results."""
    print("Starting precomputation...")
    start_time = time.time()

    # Load current data
    standings, fixtures, last_updated, data_source, load_errors = load_data()

    if load_errors and any("CRITICAL" in err for err in load_errors):
        print("CRITICAL Error loading data. Aborting precomputation.")
        return

    if not standings or (not fixtures and len(fixtures) > 0):
         print("Could not load valid standings or fixtures. Aborting precomputation.")
         return

    num_fixtures = len(fixtures)
    print(f"Loaded data: {len(standings)} teams, {num_fixtures} fixtures remaining.")

    # Initialize output structure
    output_data = {
        "metadata": {
            "precomputed_at": datetime.utcnow().isoformat() + "Z",
            "num_fixtures": num_fixtures,
            "last_data_update": last_updated,
            "data_source": data_source,
            "method_used": None # Will be filled based on execution path
        },
        "analysis_data": None # Will hold results from the chosen method
    }

    analysis_results = None # To store results from either method

    # --- Decide and Run Analysis ---
    if num_fixtures < EXHAUSTIVE_THRESHOLD:
        print(f"Running Exhaustive Analysis ({num_fixtures} < {EXHAUSTIVE_THRESHOLD} fixtures)...")
        # Note: run_exhaustive_analysis_once has its own internal progress/status
        analysis_results = run_exhaustive_analysis_once(standings, fixtures)
        if analysis_results:
            print("Exhaustive analysis completed.")
            output_data["metadata"]["method_used"] = "Exhaustive"
        else:
            print("Exhaustive analysis failed or was aborted.")
            # Decide if we should abort saving entirely if exhaustive fails
            # For now, we'll proceed but analysis_results will be None

    else: # Run Monte Carlo
        print(f"Running Monte Carlo Analysis ({num_fixtures} >= {EXHAUSTIVE_THRESHOLD} fixtures, using {NUM_SIMULATIONS_MC} simulations)...")
        output_data["metadata"]["method_used"] = "Monte Carlo"
        mc_results = {
            "overall_probabilities": None,
            "team_analysis": { "4": {}, "2": {} },
            # NOTE: Monte Carlo cannot reliably calculate 'qualification_path'
            # So, this key will be MISSING when MC is used.
        }
        mc_success = True # Flag to track if all MC parts succeed

        # MC Overall Probabilities
        print("  - Calculating MC overall probabilities...")
        mc_overall_probs = simulate_season_mc(standings, fixtures, num_simulations=NUM_SIMULATIONS_MC)
        if mc_overall_probs:
            mc_results["overall_probabilities"] = mc_overall_probs
            print("  - MC overall probabilities completed.")
        else:
            print("  - WARNING: MC overall probabilities failed.")
            mc_success = False # Mark as potentially incomplete

        # MC Team Analysis (for all teams, Top 4 & Top 2)
        team_keys = list(standings.keys())
        total_team_analyses = len(team_keys) * 2
        completed_team_analyses = 0
        print(f"  - Calculating MC team-specific analysis for {len(team_keys)} teams (Top 4 & Top 2)...")
        for team_key in team_keys:
            for target_n in [4, 2]:
                print(f"    - Analyzing {team_key} (Top {target_n})...")
                try:
                    percentage, results_df = analyze_team_mc(team_key, target_n, standings, fixtures, num_simulations=NUM_SIMULATIONS_MC)
                    mc_results["team_analysis"][str(target_n)][team_key] = {
                        'percentage': percentage,
                        'results_df': results_df.to_dict(orient='index') # Store as dict
                    }
                except Exception as e:
                     print(f"    - ERROR analyzing {team_key} (Top {target_n}): {e}")
                     mc_success = False # Mark as potentially incomplete

                completed_team_analyses += 1
                print(f"    - Completed {team_key} (Top {target_n}). Progress: {completed_team_analyses}/{total_team_analyses}")

        if mc_success:
             analysis_results = mc_results # Assign the assembled MC results
             print("Monte Carlo analysis completed.")
        else:
             print("Monte Carlo analysis completed with errors. Results might be incomplete.")
             analysis_results = mc_results # Still assign potentially incomplete results

    # --- Save Results ---
    if analysis_results is not None: # Only save if some analysis was attempted and produced a result dict
        output_data["analysis_data"] = analysis_results
        try:
            print(f"Saving analysis ({output_data['metadata']['method_used']}) to {ANALYSIS_FILE}...")
            with open(ANALYSIS_FILE, 'w') as f:
                json.dump(output_data, f, indent=4)
            print("Analysis saved successfully.")
        except IOError as e:
            print(f"ERROR: Failed to write analysis file: {e}")
        except TypeError as e:
            print(f"ERROR: Failed to serialize analysis data to JSON: {e}")
    else:
        print("No analysis results generated, skipping save.")

    end_time = time.time()
    print(f"Precomputation finished in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    precompute_analysis() # Renamed function call
