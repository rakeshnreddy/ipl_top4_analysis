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
    'Kolkata': {'Matches': 11, 'Wins': 8, 'Points': 16},
    'Rajasthan': {'Matches': 10, 'Wins': 8, 'Points': 16},
    'Chennai': {'Matches': 11, 'Wins': 6, 'Points': 12},
    'Hyderabad': {'Matches': 11, 'Wins': 6, 'Points': 12},
    'Lucknow': {'Matches': 11, 'Wins': 6, 'Points': 12},
    'Delhi': {'Matches': 11, 'Wins': 5, 'Points': 10},
    'Bangalore': {'Matches': 11, 'Wins': 4, 'Points': 8},
    'Punjab': {'Matches': 11, 'Wins': 4, 'Points': 8},
    'Mumbai': {'Matches': 12, 'Wins': 3, 'Points': 8},
    'Gujarat': {'Matches': 11, 'Wins': 4, 'Points': 8}
}

remaining_fixtures = [
    ('Delhi', 'Rajasthan'), 
    ('Hyderabad', 'Lucknow'), ('Punjab', 'Bangalore'), ('Gujarat', 'Chennai'), 
    ('Kolkata', 'Mumbai'), ('Chennai', 'Rajasthan'), ('Bangalore', 'Delhi'), 
    ('Gujarat', 'Kolkata'), ('Delhi', 'Lucknow'), ('Rajasthan', 'Punjab'), 
    ('Hyderabad', 'Gujarat'), ('Mumbai', 'Lucknow'), ('Bangalore', 'Chennai'), 
    ('Hyderabad', 'Punjab'), ('Rajasthan', 'Kolkata')
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
    all_positions = {team: [0] * 10 for team in current_standings}
    scenarios = product([0, 1], repeat=len(remaining_fixtures))
    total_scenarios = 0

    for outcome in scenarios:
        standings = {team: dict(stats) for team, stats in current_standings.items()}
        for match_result, match in zip(outcome, remaining_fixtures):
            winner = match[0] if match_result == 1 else match[1]
            loser = match[1] if winner == match[0] else match[0]
            standings[winner]['Wins'] += 1
            standings[winner]['Points'] += 2
            standings[winner]['Matches'] += 1
            standings[loser]['Matches'] += 1

        if all(standings[team]['Matches'] == total_matches_per_team[team] for team in standings):
            total_scenarios += 1
            sorted_teams = sorted(standings.items(), key=lambda x: (-x[1]['Points'], -x[1]['Wins']))
            for pos, (team, _) in enumerate(sorted_teams):
                all_positions[team][pos] += 1

    for team, positions in all_positions.items():
        current_standings[team]['Top 4 Probability'] = sum(positions[:4]) / total_scenarios * 100
        current_standings[team]['Top 2 Probability'] = sum(positions[:2]) / total_scenarios * 100

def analyze_team(team_name, top_n):
    total_matches_per_team = calculate_total_matches_per_team()
    valid_scenarios = 0
    match_wins_count = {match: {'team_a_wins': 0, 'team_b_wins': 0} for match in remaining_fixtures}

    for outcome in product([0, 1], repeat=len(remaining_fixtures)):
        updated_standings = {team: dict(stats) for team, stats in current_standings.items()}
        outcome_dict = dict(zip(remaining_fixtures, outcome))

        for match, result in outcome_dict.items():
            team_a, team_b = match
            winner = team_a if result == 1 else team_b
            loser = team_b if winner == team_a else team_a
            updated_standings[winner]['Wins'] += 1
            updated_standings[winner]['Points'] += 2
            updated_standings[winner]['Matches'] += 1
            updated_standings[loser]['Matches'] += 1

        if all(updated_standings[team]['Matches'] == total_matches_per_team[team] for team in updated_standings):
            sorted_teams = sorted(updated_standings.items(), key=lambda x: (-x[1]['Points'], -x[1]['Wins']))
            if team_name in [team for team, _ in sorted_teams[:top_n]]:
                valid_scenarios += 1
                for match, result in outcome_dict.items():
                    if result == 1:
                        match_wins_count[match]['team_a_wins'] += 1
                    else:
                        match_wins_count[match]['team_b_wins'] += 1

    for match, results in match_wins_count.items():
        total_wins = results['team_a_wins'] + results['team_b_wins']
        if total_wins > 0:
            match_wins_count[match]['Most Likely Winner'] = f"{match[0]} {100 * results['team_a_wins'] / total_wins:.2f}% | {match[1]} {100 * results['team_b_wins'] / total_wins:.2f}%"

    if valid_scenarios > 0:
        results_df = DataFrame.from_dict(match_wins_count, orient='index', columns=['Most Likely Winner'])
        results_df.index = [f"{match[0]} vs {match[1]}" for match in results_df.index]
        return 100 * valid_scenarios / (2 ** len(remaining_fixtures)), results_df
    else:
        return 0, None  # No valid scenarios


def simulate_matches(results_df):
    try:
        final_results = {team: {'Matches': stats['Matches'], 'Wins': stats['Wins'], 'Points': stats['Points']} for team, stats in current_standings.items()}

        for match, row in results_df.iterrows():
            team_a, team_b = match.split(' vs ')
            percentages = row['Most Likely Winner'].split('|')
            team_a_percentage = float(percentages[0].split()[1].strip('%'))
            team_b_percentage = float(percentages[1].split()[1].strip('%'))

            if team_a_percentage > team_b_percentage:
                winner = team_a
                loser = team_b
            elif team_a_percentage < team_b_percentage:
                winner = team_b
                loser = team_a
            else:
                winner, loser = random.choice([(team_a, team_b), (team_b, team_a)])

            final_results[winner]['Wins'] += 1
            final_results[winner]['Matches'] += 1
            final_results[winner]['Points'] += 2
            final_results[loser]['Matches'] += 1

        final_results_df = DataFrame.from_dict(final_results, orient='index')
        final_results_df.sort_values(by=['Points', 'Wins'], ascending=[False, False], inplace=True)
        return final_results_df
    except Exception as e:
        return f"An error occurred during simulation: {str(e)}"

def main():
    st.title("IPL Standings and Probability Analysis")

    simulate_season()
    df_standings = plot_standings(current_standings)
    st.table(df_standings[['Team Name', 'Matches', 'Wins', 'Points', 'Top 4 Probability', 'Top 2 Probability']])

    top_n_choice = st.radio("Select analysis depth:", ["Top 4", "Top 2"])
    top_n = 2 if top_n_choice == "Top 2" else 4

    team_name = st.selectbox("Select a team to analyze:", list(team_full_names.values()))
    if st.button("Analyze Team"):
        team_key = next(key for key, value in team_full_names.items() if value == team_name)
        percentage, team_results = analyze_team(team_key, top_n)
        if team_results is None:
            st.write(f"No data available. {team_name} cannot finish in the top {top_n} based on current standings and remaining fixtures.")
        else:
            st.write(f"{team_name} finishes in the top {top_n} in {percentage:.2f}% of scenarios.")
            st.write(f"Match outcome frequencies where the team finishes in the top {top_n}:")
            st.table(team_results)

        # Store results in session state for persistence
        st.session_state['results_df'] = team_results

    if st.button("Simulate Matches"):
        if 'results_df' in st.session_state and st.session_state['results_df'] is not None:
            final_results_df = simulate_matches(st.session_state['results_df'].copy())
            if isinstance(final_results_df, str):  # Check if the returned object is an error message
                st.error(final_results_df)
            else:
                st.write("Final Results after Simulating Matches:")
                st.table(final_results_df)
        else:
            st.write("Please analyze a team first or ensure there is valid data before simulating matches.")

if __name__ == "__main__":
    main()
