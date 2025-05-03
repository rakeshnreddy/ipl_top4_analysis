# precompute_analysis.py
import json
from ipl_analysis_app import run_exhaustive_analysis_once, load_data

def main():
    # 1) load raw data
    standings, fixtures, *_ = load_data()
    # 2) run exhaustive analysis
    analysis = run_exhaustive_analysis_once(standings, fixtures)
    # 3) write to JSON
    with open('analysis_results.json', 'w') as f:
        json.dump(analysis, f, indent=4)

if __name__ == '__main__':
    main()
