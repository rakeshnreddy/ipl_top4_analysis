import streamlit as st
import matplotlib.pyplot as plt
from itertools import product
from pandas import DataFrame

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
    ('Hyderabad', 'Lucknow'),('Punjab', 'Bangalore'), ('Gujarat', 'Chennai'), 
    ('Kolkata', 'Mumbai'),('Chennai', 'Rajasthan'), ('Bangalore', 'Delhi'), 
    ('Gujarat', 'Kolkata'),('Delhi', 'Lucknow'), ('Rajasthan', 'Punjab'), 
    ('Hyderabad', 'Gujarat'),('Mumbai', 'Lucknow'), ('Bangalore', 'Chennai'), 
    ('Hyderabad', 'Punjab'),('Rajasthan', 'Kolkata')
]

def plot_standings(standings):
    df = DataFrame(standings).T
    df.sort_values(by='Points', ascending=False, inplace=True)
    plt.figure(figsize=(10, 5))
    plt.bar(df.index, df['Points'], color='tab:blue')
    plt.xlabel('Teams')
    plt.ylabel('Points')
    plt.title('IPL Standings')
    plt.xticks(rotation=45)
    plt.tight_layout()
    return plt



def analyze_team(team_name, scenarios_to_show=3):
    # Initialize total matches per team from current standings
    total_matches_per_team = {team: stats['Matches'] for team, stats in current_standings.items()}

    # Properly accumulate total expected matches from remaining fixtures
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

st.title("Current IPL Standings")
df_standings = DataFrame(current_standings).T
df_standings.sort_values(by='Points', ascending=False, inplace=True)
st.table(df_standings)



# Assuming the function above is defined and imported or included in your Streamlit script

def main():
    st.title("IPL Season Analysis")
    mode = st.radio("Choose Mode:", ['Interactive Updates', 'Team Analysis'])

    if mode == 'Interactive Updates':
        fixture_index = st.selectbox("Select a match to update", list(range(len(remaining_fixtures))), format_func=lambda x: f"{remaining_fixtures[x][0]} vs {remaining_fixtures[x][1]}")
        winner = st.radio("Select the winner", (remaining_fixtures[fixture_index][0], remaining_fixtures[fixture_index][1]))

        if st.button("Update Result"):
            current_standings[winner]['Wins'] += 1
            current_standings[winner]['Points'] += 2
            current_standings[winner]['Matches'] += 1
            remaining_fixtures.pop(fixture_index)
            plt = plot_standings(current_standings)
            st.pyplot(plt)

    elif mode == 'Team Analysis':
        team_names = list(current_standings.keys())
        team_name = st.selectbox("Select a team for analysis:", team_names)
        if st.button("Analyze Team"):
            valid_scenarios, total_scenarios, percentage_chance, examples = analyze_team(team_name)
            st.write(f"{team_name} can finish in the top 4 in {valid_scenarios} out of {total_scenarios} scenarios ({percentage_chance:.2f}% chance).")
            for i, example in enumerate(examples, 1):
                st.subheader(f"Example {i}:")
                for result in example[0]:
                    st.write(result)
                st.write("Full standings in this scenario:")
                df = DataFrame({team: {'Matches': stats['Matches'], 'Wins': stats['Wins'], 'Points': stats['Points']} for team, stats in example[1]}).T
                df.sort_values(by='Points', ascending=False, inplace=True)
                st.table(df)

if __name__ == "__main__":
    main()
