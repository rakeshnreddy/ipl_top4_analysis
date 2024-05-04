import streamlit as st
import matplotlib.pyplot as plt
from itertools import product
from pandas import DataFrame
import numpy as np

# Define the current standings and remaining fixtures
current_standings = {
    'Rajasthan': {'Matches': 10, 'Wins': 8, 'Points': 16},
    'Kolkata': {'Matches': 10, 'Wins': 7, 'Points': 14},
    'Lucknow': {'Matches': 10, 'Wins': 6, 'Points': 12},
    'Hyderabad': {'Matches': 10, 'Wins': 6, 'Points': 12},
    'Chennai': {'Matches': 10, 'Wins': 5, 'Points': 10},
    'Delhi': {'Matches': 11, 'Wins': 5, 'Points': 10},
    'Punjab': {'Matches': 10, 'Wins': 4, 'Points': 8},
    'Gujarat': {'Matches': 10, 'Wins': 4, 'Points': 8},
    'Mumbai': {'Matches': 11, 'Wins': 3, 'Points': 6},
    'Bangalore': {'Matches': 10, 'Wins': 3, 'Points': 6}
}

remaining_fixtures = [
    ('Bangalore', 'Gujarat'), ('Punjab', 'Chennai'), 
    ('Lucknow', 'Kolkata'), ('Mumbai', 'Hyderabad'), ('Delhi', 'Rajasthan'), 
    ('Hyderabad', 'Lucknow'), ('Punjab', 'Bangalore'), ('Gujarat', 'Chennai'), 
    ('Kolkata', 'Mumbai'), ('Chennai', 'Rajasthan'), ('Bangalore', 'Delhi'), 
    ('Gujarat', 'Kolkata'), ('Delhi', 'Lucknow'), ('Rajasthan', 'Punjab'), 
    ('Hyderabad', 'Gujarat'), ('Mumbai', 'Lucknow'), ('Bangalore', 'Chennai'), 
    ('Hyderabad', 'Punjab'), ('Rajasthan', 'Kolkata')
]

def plot_standings(standings):
    df = DataFrame(standings).T
    df['Matches'] = df['Matches'].astype(int)
    df['Wins'] = df['Wins'].astype(int)
    df['Points'] = df['Points'].astype(int)
    df.sort_values(by='Points', ascending=False, inplace=True)
    plt.figure(figsize=(10, 5))
    plt.bar(df.index, df['Points'], color=plt.cm.Paired(np.arange(len(df))))
    plt.xlabel('Teams')
    plt.ylabel('Points')
    plt.title('Current IPL Standings')
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(plt)

def analyze_team(team_name, scenarios_to_show=3):
    total_matches_per_team = {team: stats['Matches'] for team, stats in current_standings.items()}
    for match in remaining_fixtures:
        team1, team2 = match
        total_matches_per_team[team1] += 1
        total_matches_per_team[team2] += 1

    scenarios = product([0, 1], repeat=len(remaining_fixtures))
    valid_scenarios = 0
    total_scenarios = 0
    example_outputs = []

    for outcome in scenarios:
        updated_standings = {team: dict(stats) for team, stats in current_standings.items()}
        match_results = []

        for match_result, match in zip(outcome, remaining_fixtures):
            winner = match[0] if match_result == 1 else match[1]
            loser = match[1] if winner == match[0] else match[0]
            updated_standings[winner]['Wins'] += 1
            updated_standings[winner]['Points'] += 2
            updated_standings[winner]['Matches'] += 1
            updated_standings[loser]['Matches'] += 1
            match_results.append(f"{match[0]} vs {match[1]}: {winner} wins")

        if all(updated_standings[team]['Matches'] == total_matches_per_team[team] for team in updated_standings):
            sorted_teams = sorted(updated_standings.items(), key=lambda x: (-x[1]['Points'], -x[1]['Wins']))
            top_teams = [team for team, _ in sorted_teams[:4]]

            if team_name in top_teams:
                valid_scenarios += 1
                if len(example_outputs) < scenarios_to_show:
                    example_outputs.append((match_results, sorted_teams))

        total_scenarios += 1

    percentage_chance = (valid_scenarios / total_scenarios) * 100 if total_scenarios > 0 else 0
    return valid_scenarios, total_scenarios, percentage_chance, example_outputs


def simulate_season():
    total_matches_per_team = {team: stats['Matches'] for team, stats in current_standings.items()}
    for match in remaining_fixtures:
        team1, team2 = match
        total_matches_per_team[team1] += 1
        total_matches_per_team[team2] += 1

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

def main():
    st.title("Current IPL Standings with Top 4 Probability")
    simulate_season()  # Calculate and update probabilities
    
    # Convert standings to DataFrame
    df_standings = DataFrame(current_standings).T
    
    # Ensure data types for Matches, Wins, and Points are integers
    df_standings['Matches'] = df_standings['Matches'].astype(int)
    df_standings['Wins'] = df_standings['Wins'].astype(int)
    df_standings['Points'] = df_standings['Points'].astype(int)
    
    # Format probability column with percentages and two decimal places
    df_standings['Top 4 Probability'] = df_standings['Top 4 Probability'].astype(float).map('{:.2f}%'.format)
    
    # Sort standings by Points
    df_standings.sort_values(by='Points', ascending=False, inplace=True)
    
    # Display the DataFrame as a table in Streamlit
    st.table(df_standings)
    plot_standings(current_standings)

    team_name = st.selectbox("Select a team to analyze:", list(current_standings.keys()))
    if st.button("Analyze Team"):
        valid_scenarios, total_scenarios, percentage_chance, examples = analyze_team(team_name)
        st.write(f"{team_name} has a {percentage_chance:.2f}% chance to finish in the top 4, based on {valid_scenarios} out of {total_scenarios} valid scenarios.")
        for i, example in enumerate(examples, 1):
            st.subheader(f"Example Scenario {i} where {team_name} finishes in the top 4:")
            for result in example[0]:
                st.write(result)
            st.write("Standings in this scenario:")
            df = DataFrame({team: {'Matches': stats['Matches'], 'Wins': stats['Wins'], 'Points': stats['Points']} for team, stats in example[1]}).T
            df.sort_values(by='Points', ascending=False, inplace=True)
            st.table(df)

if __name__ == "__main__":
    main()
