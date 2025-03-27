import streamlit as st
from pandas import DataFrame
import random

# Team colors and full names for IPL teams
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

def simulate_season(num_simulations=10000):
    total_matches_per_team = calculate_total_matches_per_team()
    # Initialize counters for top 4 and top 2 finishes for each team
    counts = {team: {'top4': 0, 'top2': 0} for team in current_standings}
    
    # Monte Carlo simulation for season outcomes
    for _ in range(num_simulations):
        # Create a fresh copy of current standings for this simulation
        standings = {team: dict(current_standings[team]) for team in current_standings}
        # Simulate each remaining fixture with a random outcome
        for match in remaining_fixtures:
            outcome = random.choice([0, 1])
            team_a, team_b = match
            winner = team_a if outcome == 1 else team_b
            loser = team_b if outcome == 1 else team_a
            standings[winner]['Wins'] += 1
            standings[winner]['Points'] += 2
            standings[winner]['Matches'] += 1
            standings[loser]['Matches'] += 1
        
        # Confirm that every team has played all its matches
        if all(standings[team]['Matches'] == total_matches_per_team[team] for team in standings):
            # Sort teams by Points and Wins
            sorted_teams = sorted(standings.items(), key=lambda x: (-x[1]['Points'], -x[1]['Wins']))
            top4_teams = [team for team, _ in sorted_teams[:4]]
            top2_teams = [team for team, _ in sorted_teams[:2]]
            for team in current_standings:
                if team in top4_teams:
                    counts[team]['top4'] += 1
                if team in top2_teams:
                    counts[team]['top2'] += 1
    
    # Update current standings with probabilities from simulations
    for team in current_standings:
        current_standings[team]['Top 4 Probability'] = (counts[team]['top4'] / num_simulations) * 100
        current_standings[team]['Top 2 Probability'] = (counts[team]['top2'] / num_simulations) * 100
    
    return plot_standings(current_standings)

def analyze_team(team_name, top_n, num_simulations=10000):
    total_matches_per_team = calculate_total_matches_per_team()
    valid_scenarios = 0
    match_wins_count = {match: {'team_a_wins': 0, 'team_b_wins': 0} for match in remaining_fixtures}
    
    # Monte Carlo simulation for analyzing team performance in finishing in the top n
    for _ in range(num_simulations):
        updated_standings = {team: dict(current_standings[team]) for team in current_standings}
        outcome_dict = {}
        for match in remaining_fixtures:
            outcome = random.choice([0, 1])
            outcome_dict[match] = outcome
            team_a, team_b = match
            winner = team_a if outcome == 1 else team_b
            loser = team_b if outcome == 1 else team_a
            updated_standings[winner]['Wins'] += 1
            updated_standings[winner]['Points'] += 2
            updated_standings[winner]['Matches'] += 1
            updated_standings[loser]['Matches'] += 1
        
        if all(updated_standings[team]['Matches'] == total_matches_per_team[team] for team in updated_standings):
            sorted_teams = sorted(updated_standings.items(), key=lambda x: (-x[1]['Points'], -x[1]['Wins']))
            top_n_teams = [team for team, _ in sorted_teams[:top_n]]
            if team_name in top_n_teams:
                valid_scenarios += 1
                for match, result in outcome_dict.items():
                    if result == 1:
                        match_wins_count[match]['team_a_wins'] += 1
                    else:
                        match_wins_count[match]['team_b_wins'] += 1
    
    if valid_scenarios > 0:
        results_data = {}
        for match, counts_dict in match_wins_count.items():
            total = counts_dict['team_a_wins'] + counts_dict['team_b_wins']
            if total > 0:
                if counts_dict['team_a_wins'] > counts_dict['team_b_wins']:
                    outcome_str = f"{match[0]} wins"
                elif counts_dict['team_b_wins'] > counts_dict['team_a_wins']:
                    outcome_str = f"{match[1]} wins"
                else:
                    outcome_str = "Result doesn't matter"
            else:
                outcome_str = "Result doesn't matter"
            results_data[match] = outcome_str
        
        results_df = DataFrame({
            'Outcome': [results_data[match] for match in remaining_fixtures]
        }, index=[f"{match[0]} vs {match[1]}" for match in remaining_fixtures])
        return 100 * valid_scenarios / num_simulations, results_df
    else:
        return 0, DataFrame(columns=['Outcome'])

def simulate_matches(results_df, team_name):
    try:
        final_results = {team: {
            'Matches': current_standings[team]['Matches'],
            'Wins': current_standings[team]['Wins'],
            'Points': current_standings[team]['Points'],
            'priority': 1  # Default priority for sorting
        } for team in current_standings}
        final_results[team_name]['priority'] = 0  # Give the analyzed team a higher priority
        
        match_results = []
        for match, row in results_df.iterrows():
            team_a, team_b = match.split(' vs ')
            outcome = row['Outcome']
            if "wins" in outcome:
                winner = team_a if team_a in outcome else team_b
                loser = team_b if winner == team_a else team_a
            elif "Result doesn't matter" in outcome:
                winner, loser = random.choice([(team_a, team_b), (team_b, team_a)])
            else:
                continue
            final_results[winner]['Wins'] += 1
            final_results[winner]['Matches'] += 1
            final_results[winner]['Points'] += 2
            final_results[loser]['Matches'] += 1
            match_result_str = f"{winner} defeats {loser}"
            match_results.append(match_result_str)
        
        final_results_df = DataFrame.from_dict(final_results, orient='index')
        final_results_df.sort_values(by=['Points', 'priority', 'Wins'], ascending=[False, True, False], inplace=True)
        return match_results, final_results_df
    except Exception as e:
        return f"An error occurred during simulation: {str(e)}", None

def main():
    st.title("IPL Standings and Probability Analysis")

    # Select a team for analysis using its full name
    full_team_name = st.selectbox("Select a team to analyze:", list(team_full_names.values()))
    team_key = next(key for key, value in team_full_names.items() if value == full_team_name)
    
    # Simulate the season and display updated standings with probabilities
    df_standings = simulate_season(num_simulations=10000000)
    st.table(df_standings[['Team Name', 'Matches', 'Wins', 'Points', 'Top 4 Probability', 'Top 2 Probability']])
    
    top_n_choice = st.radio("Select analysis depth:", ["Top 4", "Top 2"])
    top_n = 2 if top_n_choice == "Top 2" else 4
    
    if st.button("Analyze Team"):
        percentage, team_results = analyze_team(team_key, top_n, num_simulations=10000)
        if team_results.empty:
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
