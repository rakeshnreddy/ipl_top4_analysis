import streamlit as st
from itertools import product
from pandas import DataFrame
import random


# Team colors and full names for IPL teams
team_full_names = {
    'Rajasthan': 'Rajasthan Royals',
    'Kolkata': 'Kolkata Knight Riders',
    'Lucknow': 'Lucknow Super Giants',
    'Hyderabad': 'Sunrisers Hyderabad',
    'Chennai': 'Chennai Super Kings',
    'Delhi': 'Delhi Capitals',
    'Punjab': 'Punjab Kings',
    'Gujarat': 'Gujarat Titans',
    'Mumbai': 'Mumbai Indians',
    'Bangalore': 'Royal Challengers Bangalore'
}

# Define the current standings and remaining fixtures
current_standings = {
    'Hyderabad': {'Matches': 1, 'Wins': 1, 'Points': 2},   # Sunrisers Hyderabad
    'Bangalore': {'Matches': 1, 'Wins': 1, 'Points': 2},     # Royal Challengers Bengaluru
    'Punjab': {'Matches': 1, 'Wins': 1, 'Points': 2},        # Punjab Kings
    'Chennai': {'Matches': 1, 'Wins': 1, 'Points': 2},       # Chennai Super Kings
    'Delhi': {'Matches': 1, 'Wins': 1, 'Points': 2},         # Delhi Capitals
    'Kolkata': {'Matches': 2, 'Wins': 1, 'Points': 2},       # Kolkata Knight Riders
    'Lucknow': {'Matches': 1, 'Wins': 0, 'Points': 0},       # Lucknow Super Giants
    'Mumbai': {'Matches': 1, 'Wins': 0, 'Points': 0},        # Mumbai Indians
    'Gujarat': {'Matches': 1, 'Wins': 0, 'Points': 0},       # Gujarat Titans
    'Rajasthan': {'Matches': 2, 'Wins': 0, 'Points': 0}      # Rajasthan Royals
}


remaining_fixtures = [
    ('Hyderabad', 'Lucknow'),      # Match 7: 27 Mar 19:30 – Sunrisers Hyderabad (H) vs Lucknow Super Giants
    ('Chennai', 'Bangalore'),      # Match 8: 28 Mar 19:30 – Chennai Super Kings (H) vs Royal Challengers Bangalore
    ('Gujarat', 'Mumbai'),         # Match 9: 29 Mar 19:30 – Gujarat Titans (H) vs Mumbai Indians
    ('Delhi', 'Hyderabad'),        # Match 10: 30 Mar 15:30 – Delhi Capitals (H) vs Sunrisers Hyderabad
    ('Rajasthan', 'Chennai'),      # Match 11: 30 Mar 19:30 – Rajasthan Royals (H) vs Chennai Super Kings
    ('Mumbai', 'Kolkata'),         # Match 12: 31 Mar 19:30 – Mumbai Indians (H) vs Kolkata Knight Riders
    ('Lucknow', 'Punjab'),         # Match 13: 1 Apr 19:30 – Lucknow Super Giants (H) vs Punjab Kings
    ('Bangalore', 'Gujarat'),      # Match 14: 2 Apr 19:30 – Royal Challengers Bangalore (H) vs Gujarat Titans
    ('Kolkata', 'Hyderabad'),      # Match 15: 3 Apr 19:30 – Kolkata Knight Riders (H) vs Sunrisers Hyderabad
    ('Lucknow', 'Mumbai'),         # Match 16: 4 Apr 19:30 – Lucknow Super Giants (H) vs Mumbai Indians
    ('Chennai', 'Delhi'),          # Match 17: 5 Apr 15:30 – Chennai Super Kings (H) vs Delhi Capitals
    ('Punjab', 'Rajasthan'),       # Match 18: 5 Apr 19:30 – Punjab Kings (H) vs Rajasthan Royals
    ('Kolkata', 'Lucknow'),        # Match 19: 6 Apr 15:30 – Kolkata Knight Riders (H) vs Lucknow Super Giants
    ('Hyderabad', 'Gujarat'),      # Match 20: 6 Apr 19:30 – Sunrisers Hyderabad (H) vs Gujarat Titans
    ('Mumbai', 'Bangalore'),       # Match 21: 7 Apr 19:30 – Mumbai Indians (H) vs Royal Challengers Bangalore
    ('Punjab', 'Chennai'),         # Match 22: 8 Apr 19:30 – Punjab Kings (H) vs Chennai Super Kings
    ('Gujarat', 'Rajasthan'),      # Match 23: 9 Apr 19:30 – Gujarat Titans (H) vs Rajasthan Royals
    ('Bangalore', 'Delhi'),        # Match 24: 10 Apr 19:30 – Royal Challengers Bangalore (H) vs Delhi Capitals
    ('Chennai', 'Kolkata'),        # Match 25: 11 Apr 19:30 – Chennai Super Kings (H) vs Kolkata Knight Riders
    ('Lucknow', 'Gujarat'),        # Match 26: 12 Apr 15:30 – Lucknow Super Giants (H) vs Gujarat Titans
    ('Hyderabad', 'Punjab'),       # Match 27: 12 Apr 19:30 – Sunrisers Hyderabad (H) vs Punjab Kings
    ('Rajasthan', 'Bangalore'),    # Match 28: 13 Apr 15:30 – Rajasthan Royals (H) vs Royal Challengers Bangalore
    ('Delhi', 'Mumbai'),           # Match 29: 13 Apr 19:30 – Delhi Capitals (H) vs Mumbai Indians
    ('Lucknow', 'Chennai'),        # Match 30: 14 Apr 19:30 – Lucknow Super Giants (H) vs Chennai Super Kings
    ('Punjab', 'Kolkata'),         # Match 31: 15 Apr 19:30 – Punjab Kings (H) vs Kolkata Knight Riders
    ('Delhi', 'Rajasthan'),        # Match 32: 16 Apr 19:30 – Delhi Capitals (H) vs Rajasthan Royals
    ('Mumbai', 'Hyderabad'),       # Match 33: 17 Apr 19:30 – Mumbai Indians (H) vs Sunrisers Hyderabad
    ('Bangalore', 'Punjab'),       # Match 34: 18 Apr 19:30 – Royal Challengers Bangalore (H) vs Punjab Kings
    ('Gujarat', 'Delhi'),          # Match 35: 19 Apr 15:30 – Gujarat Titans (H) vs Delhi Capitals
    ('Rajasthan', 'Lucknow'),      # Match 36: 19 Apr 19:30 – Rajasthan Royals (H) vs Lucknow Super Giants
    ('Punjab', 'Bangalore'),       # Match 37: 20 Apr 15:30 – Punjab Kings (H) vs Royal Challengers Bangalore
    ('Mumbai', 'Chennai'),         # Match 38: 20 Apr 19:30 – Mumbai Indians (H) vs Chennai Super Kings
    ('Kolkata', 'Gujarat'),        # Match 39: 21 Apr 19:30 – Kolkata Knight Riders (H) vs Gujarat Titans
    ('Lucknow', 'Delhi'),          # Match 40: 22 Apr 19:30 – Lucknow Super Giants (H) vs Delhi Capitals
    ('Hyderabad', 'Mumbai'),       # Match 41: 23 Apr 19:30 – Sunrisers Hyderabad (H) vs Mumbai Indians
    ('Bangalore', 'Rajasthan'),    # Match 42: 24 Apr 19:30 – Royal Challengers Bangalore (H) vs Rajasthan Royals
    ('Chennai', 'Hyderabad'),      # Match 43: 25 Apr 19:30 – Chennai Super Kings (H) vs Sunrisers Hyderabad
    ('Kolkata', 'Punjab'),         # Match 44: 26 Apr 19:30 – Kolkata Knight Riders (H) vs Punjab Kings
    ('Mumbai', 'Lucknow'),         # Match 45: 27 Apr 15:30 – Mumbai Indians (H) vs Lucknow Super Giants
    ('Delhi', 'Bangalore'),        # Match 46: 27 Apr 19:30 – Delhi Capitals (H) vs Royal Challengers Bangalore
    ('Rajasthan', 'Gujarat'),      # Match 47: 28 Apr 19:30 – Rajasthan Royals (H) vs Gujarat Titans
    ('Delhi', 'Kolkata'),          # Match 48: 29 Apr 19:30 – Delhi Capitals (H) vs Kolkata Knight Riders
    ('Chennai', 'Punjab'),         # Match 49: 30 Apr 19:30 – Chennai Super Kings (H) vs Punjab Kings
    ('Rajasthan', 'Mumbai'),       # Match 50: 1 May 19:30 – Rajasthan Royals (H) vs Mumbai Indians
    ('Gujarat', 'Hyderabad'),      # Match 51: 2 May 19:30 – Gujarat Titans (H) vs Sunrisers Hyderabad
    ('Bangalore', 'Chennai'),      # Match 52: 3 May 19:30 – Royal Challengers Bangalore (H) vs Chennai Super Kings
    ('Kolkata', 'Rajasthan'),      # Match 53: 4 May 15:30 – Kolkata Knight Riders (H) vs Rajasthan Royals
    ('Punjab', 'Lucknow'),         # Match 54: 4 May 19:30 – Punjab Kings (H) vs Lucknow Super Giants
    ('Hyderabad', 'Delhi'),        # Match 55: 5 May 19:30 – Sunrisers Hyderabad (H) vs Delhi Capitals
    ('Mumbai', 'Gujarat'),         # Match 56: 6 May 19:30 – Mumbai Indians (H) vs Gujarat Titans
    ('Kolkata', 'Chennai'),        # Match 57: 7 May 19:30 – Kolkata Knight Riders (H) vs Chennai Super Kings
    ('Punjab', 'Delhi'),           # Match 58: 8 May 19:30 – Punjab Kings (H) vs Delhi Capitals
    ('Lucknow', 'Bangalore'),      # Match 59: 9 May 19:30 – Lucknow Super Giants (H) vs Royal Challengers Bangalore
    ('Hyderabad', 'Kolkata'),      # Match 60: 10 May 19:30 – Sunrisers Hyderabad (H) vs Kolkata Knight Riders
    ('Punjab', 'Mumbai'),          # Match 61: 11 May 15:30 – Punjab Kings (H) vs Mumbai Indians
    ('Delhi', 'Gujarat'),          # Match 62: 11 May 19:30 – Delhi Capitals (H) vs Gujarat Titans
    ('Chennai', 'Rajasthan'),      # Match 63: 12 May 19:30 – Chennai Super Kings (H) vs Rajasthan Royals
    ('Bangalore', 'Hyderabad'),    # Match 64: 13 May 19:30 – Royal Challengers Bangalore (H) vs Sunrisers Hyderabad
    ('Gujarat', 'Lucknow'),        # Match 65: 14 May 19:30 – Gujarat Titans (H) vs Lucknow Super Giants
    ('Mumbai', 'Delhi'),           # Match 66: 15 May 19:30 – Mumbai Indians (H) vs Delhi Capitals
    ('Rajasthan', 'Punjab'),       # Match 67: 16 May 19:30 – Rajasthan Royals (H) vs Punjab Kings
    ('Bangalore', 'Kolkata'),      # Match 68: 17 May 19:30 – Royal Challengers Bangalore (H) vs Kolkata Knight Riders
    ('Gujarat', 'Chennai'),        # Match 69: 18 May 15:30 – Gujarat Titans (H) vs Chennai Super Kings
    ('Lucknow', 'Hyderabad')       # Match 70: 18 May 19:30 – Lucknow Super Giants (H) vs Sunrisers Hyderabad
]

def calculate_total_matches_per_team():
    total_matches = {team: stats['Matches'] for team, stats in current_standings.items()}
    for team1, team2 in remaining_fixtures:
        total_matches[team1] += 1
        total_matches[team2] += 1
    return total_matches

def plot_standings(standings):
    df = DataFrame(standings).T
    df = df.astype({'Matches': 'int', 'Wins': 'int', 'Points': 'int'})
    df.sort_values(by='Points', ascending=False, inplace=True)
    df['Team Name'] = df.index.map(lambda x: team_full_names[x])
    return df

def simulate_season():
    total_matches_per_team = calculate_total_matches_per_team()
    scenarios = list(product([0, 1], repeat=len(remaining_fixtures)))

    # Initialize probabilities
    for team in current_standings:
        current_standings[team]['Top 4 Probability'] = 0
        current_standings[team]['Top 2 Probability'] = 0

    for team_priority in current_standings:
        top_4_counts = 0
        top_2_counts = 0
        total_scenarios = 0

        for outcome in scenarios:
            standings = {t: dict(stats) for t, stats in current_standings.items()}
            for match_result, match in zip(outcome, remaining_fixtures):
                winner = match[0] if match_result == 1 else match[1]
                loser = match[1] if winner == match[0] else match[0]
                standings[winner]['Wins'] += 1
                standings[winner]['Points'] += 2
                standings[winner]['Matches'] += 1
                standings[loser]['Matches'] += 1

            # Ensure all matches are counted correctly
            if all(standings[t]['Matches'] == total_matches_per_team[t] for t in standings):
                total_scenarios += 1
                sorted_teams = sorted(standings.items(), key=lambda x: (-x[1]['Points'], x[0] != team_priority, -x[1]['Wins']))
                top_4_teams = sorted_teams[:4]
                top_2_teams = sorted_teams[:2]

                if team_priority in [t[0] for t in top_4_teams]:
                    top_4_counts += 1
                if team_priority in [t[0] for t in top_2_teams]:
                    top_2_counts += 1

        # Update probabilities for the team being analyzed
        if total_scenarios > 0:
            current_standings[team_priority]['Top 4 Probability'] = (top_4_counts / total_scenarios) * 100
            current_standings[team_priority]['Top 2 Probability'] = (top_2_counts / total_scenarios) * 100

    return plot_standings(current_standings)



def analyze_team(team_name, top_n):
    total_matches_per_team = calculate_total_matches_per_team()
    valid_scenarios = 0
    match_wins_count = {match: {'team_a_wins': 0, 'team_b_wins': 0} for match in remaining_fixtures}

    # Generate all possible outcomes of remaining matches
    for outcome in product([0, 1], repeat=len(remaining_fixtures)):
        updated_standings = {team: dict(stats) for team, stats in current_standings.items()}
        outcome_dict = dict(zip(remaining_fixtures, outcome))

        # Apply the results of each match outcome
        for match, result in outcome_dict.items():
            team_a, team_b = match
            winner = team_a if result == 1 else team_b
            loser = team_b if winner == team_a else team_a
            updated_standings[winner]['Wins'] += 1
            updated_standings[winner]['Points'] += 2
            updated_standings[loser]['Matches'] += 1
            updated_standings[winner]['Matches'] += 1

        # Check if standings are complete
        if all(updated_standings[team]['Matches'] == total_matches_per_team[team] for team in updated_standings):
            sorted_teams = sorted(updated_standings.items(), key=lambda x: (-x[1]['Points'], x[0] != team_name, -x[1]['Wins']))
            if team_name in [team for team, _ in sorted_teams[:top_n]]:
                valid_scenarios += 1
                for match, result in outcome_dict.items():
                    if result == 1:
                        match_wins_count[match]['team_a_wins'] += 1
                    else:
                        match_wins_count[match]['team_b_wins'] += 1

    if valid_scenarios > 0:
        for match, results in match_wins_count.items():
            total_wins = results['team_a_wins'] + results['team_b_wins']
            if total_wins > 0:
                results['Outcome'] = f"{match[0]} wins" if results['team_a_wins'] > results['team_b_wins'] else f"{match[1]} wins"
                if results['team_a_wins'] == results['team_b_wins']:
                    results['Outcome'] = "Result doesn't matter"
            else:
                results['Outcome'] = "Result doesn't matter"

        results_df = DataFrame.from_dict(match_wins_count, orient='index', columns=['Most Likely Winner', 'Outcome'])
        results_df.index = [f"{match[0]} vs {match[1]}" for match in results_df.index]
        return 100 * valid_scenarios / (2 ** len(remaining_fixtures)), results_df
    else:
        return 0, DataFrame(columns=['Most Likely Winner', 'Outcome'])



def simulate_matches(results_df, team_name):
    try:
        # Initialize the final results from current standings
        final_results = {team: {
            'Matches': current_standings[team]['Matches'],
            'Wins': current_standings[team]['Wins'],
            'Points': current_standings[team]['Points'],
            'priority': 1  # Default priority for all other teams
        } for team in current_standings}

        # Set a higher priority for the analyzed team
        final_results[team_name]['priority'] = 0

        match_results = []  # List to store the results of each simulated match

        for match, row in results_df.iterrows():
            team_a, team_b = match.split(' vs ')
            outcome = row['Outcome']

            if "wins" in outcome:
                winner = team_a if team_a in outcome else team_b
                loser = team_b if winner == team_a else team_a
            elif "Result doesn't matter" in outcome:
                # Randomly decide the winner if the result doesn't matter
                winner, loser = random.choice([(team_a, team_b), (team_b, team_a)])
            else:
                continue  # Skip if the outcome format is unexpected

            final_results[winner]['Wins'] += 1
            final_results[winner]['Matches'] += 1
            final_results[winner]['Points'] += 2
            final_results[loser]['Matches'] += 1

            match_result_str = f"{winner} defeats {loser}"
            match_results.append(match_result_str)

        # Create a DataFrame from the final results dictionary
        final_results_df = DataFrame.from_dict(final_results, orient='index')
        
        # Sorting by points first, then by priority in case of ties, and then by wins
        final_results_df.sort_values(by=['Points', 'priority', 'Wins'], ascending=[False, True, False], inplace=True)

        return match_results, final_results_df
    except Exception as e:
        return f"An error occurred during simulation: {str(e)}", None


def main():
    st.title("IPL Standings and Probability Analysis")

    # Get full team name from user selection
    full_team_name = st.selectbox("Select a team to analyze:", list(team_full_names.values()))

    # Convert full team name to the key used in standings
    team_key = next(key for key, value in team_full_names.items() if value == full_team_name)

    # Call simulate_season to populate probabilities
    simulate_season()
    df_standings = plot_standings(current_standings)
    st.table(df_standings[['Team Name', 'Matches', 'Wins', 'Points', 'Top 4 Probability', 'Top 2 Probability']])

    top_n_choice = st.radio("Select analysis depth:", ["Top 4", "Top 2"])
    top_n = 2 if top_n_choice == "Top 2" else 4

    if st.button("Analyze Team"):
        percentage, team_results = analyze_team(team_key, top_n)
        if team_results is None:
            st.write(f"No data available. {full_team_name} cannot finish in the top {top_n} based on current standings and remaining fixtures.")
        else:
            st.write(f"{full_team_name} finishes in the top {top_n} in {percentage:.2f}% of scenarios.")
            st.table(team_results[['Outcome']])
        st.session_state['results_df'] = team_results

    if st.button("Simulate Matches"):
        if 'results_df' in st.session_state and st.session_state['results_df'] is not None:
            match_results, final_results_df = simulate_matches(st.session_state['results_df'].copy(), team_key)
            if isinstance(match_results, str):
                st.error(match_results)
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Match Results:")
                    for result in match_results:
                        st.write(result)
                with col2:
                    st.write("Final Points Table after Simulating Matches:")
                    st.table(final_results_df)
        else:
            st.write("Please analyze a team first or ensure there is valid data before simulating matches.")

if __name__ == "__main__":
    main()
