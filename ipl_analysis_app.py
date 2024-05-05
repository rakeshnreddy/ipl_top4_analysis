import streamlit as st
import matplotlib.pyplot as plt
from itertools import product
from pandas import DataFrame
import numpy as np

# Team colors and full names for IPL teams
team_colors = {
    'Rajasthan': '#4B0082',
    'Kolkata': '#800080',
    'Lucknow': '#808000',
    'Hyderabad': '#FF4500',
    'Chennai': '#FFFF00',
    'Delhi': '#00008B',
    'Punjab': '#DC143C',
    'Gujarat': '#00BFFF',
    'Mumbai': '#0000CD',
    'Bangalore': '#B22222'
}

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
    'Hyderabad': {'Matches': 10, 'Wins': 6, 'Points': 12},
    'Lucknow': {'Matches': 11, 'Wins': 6, 'Points': 12},
    'Delhi': {'Matches': 11, 'Wins': 5, 'Points': 10},
    'Bangalore': {'Matches': 11, 'Wins': 4, 'Points': 8},
    'Punjab': {'Matches': 11, 'Wins': 4, 'Points': 8},
    'Gujarat': {'Matches': 11, 'Wins': 4, 'Points': 8},
    'Mumbai': {'Matches': 11, 'Wins': 3, 'Points': 6}
    
}

remaining_fixtures = [
    ('Mumbai', 'Hyderabad'), ('Delhi', 'Rajasthan'), 
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
    df['Team Name'] = df.index.map(team_full_names)  # Map abbreviated names to full names
    colors = df.index.map(team_colors)  # Map teams to their colors

    #plt.figure(figsize=(12, 6))
    #plt.bar(df['Team Name'], df['Points'], color=colors)
    #plt.xlabel('Teams')
    #plt.ylabel('Points')
    #plt.title('Current IPL Standings')
    #plt.xticks(rotation=45)
    #plt.tight_layout()
    #st.pyplot(plt)

    return df  # Return DataFrame for additional use


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
    df_standings = plot_standings(current_standings)  # Use the modified plotting function
    
    # Display the DataFrame with full team names and probabilities formatted
    df_standings['Top 4 Probability'] = df_standings['Top 4 Probability'].astype(float).map('{:.2f}%'.format)
    st.table(df_standings[['Team Name', 'Matches', 'Wins', 'Points', 'Top 4 Probability']])

    team_name = st.selectbox("Select a team to analyze:", list(team_full_names.values()))
    if st.button("Analyze Team"):
        # Adjust the analyze_team call to handle full names
        team_key = [key for key, value in team_full_names.items() if value == team_name][0]
        valid_scenarios, total_scenarios, percentage_chance, examples = analyze_team(team_key)
        st.write(f"{team_name} has a {percentage_chance:.2f}% chance to finish in the top 4, based on {valid_scenarios} out of {total_scenarios} valid scenarios.")
        for i, example in enumerate(examples, 1):
            st.subheader(f"Example Scenario {i} where {team_name} finishes in the top 4:")
            for result in example[0]:
                st.write(result)
            st.write("Standings in this scenario:")
            df_example = DataFrame({team: {'Matches': stats['Matches'], 'Wins': stats['Wins'], 'Points': stats['Points']} for team, stats in example[1]}).T
            df_example.sort_values(by='Points', ascending=False, inplace=True)
            st.table(df_example)

if __name__ == "__main__":
    main()
