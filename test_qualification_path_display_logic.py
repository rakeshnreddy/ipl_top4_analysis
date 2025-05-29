import unittest

# Helper function that encapsulates the core logic
def get_qualification_path_messages(analysis_method_used, analysis_data, team_key, full_team_name, top_n):
    messages = []

    # st.subheader(f"Qualification Path for {full_team_name} (Top {top_n})") # This is outside the core logic being tested

    if analysis_method_used.startswith("Exhaustive"):
        # st.caption("Minimum wins analysis (Exhaustive method only).") # This is a direct st call, not part of core message logic for now
        if analysis_data and "qualification_path" in analysis_data:
            try:
                # Ensure str(top_n) is used as a key, as in the original Streamlit app
                path_data = analysis_data["qualification_path"][str(top_n)][team_key]
                possible_wins = path_data.get("possible")
                guaranteed_wins = path_data.get("guaranteed")
                target_matches = path_data.get("target_matches", "N/A")

                messages.append(('write', f"**Remaining Matches for {full_team_name}:** {target_matches}"))

                if isinstance(possible_wins, int):
                    messages.append(('success', f"**Possible Qualification:** Win **{possible_wins}** match(es) (with favorable results)."))
                elif possible_wins is None:
                    messages.append(('error', f"**Possible Qualification:** Cannot qualify."))
                else:
                    messages.append(('warning', f"**Possible Qualification:** Analysis result: {possible_wins}"))

                if isinstance(guaranteed_wins, int):
                    messages.append(('success', f"**Guaranteed Qualification:** Win **{guaranteed_wins}** match(es) (irrespective of other results)."))
                elif guaranteed_wins is None and possible_wins is not None:
                    messages.append(('info', f"**Guaranteed Qualification:** Cannot guarantee qualification based solely on own wins."))
                elif guaranteed_wins is None and possible_wins is None:
                    pass # Error already shown by possible_wins block
                else: 
                    messages.append(('warning', f"**Guaranteed Qualification:** Analysis result: {guaranteed_wins}"))
            except KeyError:
                messages.append(('error', f"Exhaustive qualification path data not found for {full_team_name} (Top {top_n}) in precomputed results."))
            except Exception as e: # Should ideally not be hit if data is mocked correctly, but good to have
                messages.append(('error', f"An error occurred while displaying qualification path data: {e}"))
        else:
            messages.append(('warning', "Exhaustive qualification path data structure is missing in precomputed results."))

    elif analysis_method_used.startswith("Monte Carlo"):
        messages.append(('info', "Qualification Path analysis (minimum/guaranteed wins) is only available with the Exhaustive analysis method. The current data was computed using Monte Carlo."))
    else: 
        messages.append(('info', f"Qualification Path data is not available because the analysis method used was '{analysis_method_used}' or data is incomplete."))

    # st.markdown("---") # This is outside the core logic
    return messages

class TestQualificationPathLogic(unittest.TestCase):
    def setUp(self):
        self.team_key = "TeamA"
        self.full_team_name = "Team A Full Name"
        self.top_n = 4

    def test_scenario1_monte_carlo_method(self):
        analysis_method_used = "Monte Carlo"
        analysis_data = None
        expected_messages = [
            ('info', "Qualification Path analysis (minimum/guaranteed wins) is only available with the Exhaustive analysis method. The current data was computed using Monte Carlo.")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

    def test_scenario2_exhaustive_complete_data(self):
        analysis_method_used = "Exhaustive"
        analysis_data = {
            "qualification_path": {
                str(self.top_n): {
                    self.team_key: {
                        "possible": 2,
                        "guaranteed": 1,
                        "target_matches": 3
                    }
                }
            }
        }
        expected_messages = [
            ('write', f"**Remaining Matches for {self.full_team_name}:** 3"),
            ('success', f"**Possible Qualification:** Win **2** match(es) (with favorable results)."),
            ('success', f"**Guaranteed Qualification:** Win **1** match(es) (irrespective of other results).")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

    def test_scenario3_exhaustive_qualification_path_key_missing(self):
        analysis_method_used = "Exhaustive"
        analysis_data = {} # qualification_path key is missing
        expected_messages = [
            ('warning', "Exhaustive qualification path data structure is missing in precomputed results.")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

    def test_scenario4_exhaustive_team_or_topn_data_missing(self):
        analysis_method_used = "Exhaustive"
        analysis_data = {
            "qualification_path": {
                # str(self.top_n) might be missing or self.team_key might be missing
                str(self.top_n): {} # Empty dict for the top_n level
            }
        }
        expected_messages = [
            ('error', f"Exhaustive qualification path data not found for {self.full_team_name} (Top {self.top_n}) in precomputed results.")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

        # Another case for KeyError: top_n key itself is missing
        analysis_data_alt = {"qualification_path": {}}
        result_alt = get_qualification_path_messages(analysis_method_used, analysis_data_alt, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result_alt, expected_messages)


    def test_scenario5_exhaustive_possible_wins_none(self):
        analysis_method_used = "Exhaustive"
        analysis_data = {
            "qualification_path": {
                str(self.top_n): {
                    self.team_key: {
                        "possible": None,
                        "guaranteed": None,
                        "target_matches": 3
                    }
                }
            }
        }
        expected_messages = [
            ('write', f"**Remaining Matches for {self.full_team_name}:** 3"),
            ('error', f"**Possible Qualification:** Cannot qualify.")
            # No message for guaranteed_wins if possible_wins is None and guaranteed_wins is None
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

    def test_scenario6_exhaustive_guaranteed_wins_none_possible_int(self):
        analysis_method_used = "Exhaustive"
        analysis_data = {
            "qualification_path": {
                str(self.top_n): {
                    self.team_key: {
                        "possible": 2,
                        "guaranteed": None,
                        "target_matches": 3
                    }
                }
            }
        }
        expected_messages = [
            ('write', f"**Remaining Matches for {self.full_team_name}:** 3"),
            ('success', f"**Possible Qualification:** Win **2** match(es) (with favorable results)."),
            ('info', f"**Guaranteed Qualification:** Cannot guarantee qualification based solely on own wins.")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

    def test_scenario7_unknown_method(self):
        analysis_method_used = "Unknown"
        analysis_data = {}
        expected_messages = [
            ('info', f"Qualification Path data is not available because the analysis method used was '{analysis_method_used}' or data is incomplete.")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

    def test_scenario8_exhaustive_possible_wins_unexpected_type(self):
        analysis_method_used = "Exhaustive"
        analysis_data = {
            "qualification_path": {
                str(self.top_n): {
                    self.team_key: {
                        "possible": "error_val",
                        "guaranteed": 1,
                        "target_matches": 3
                    }
                }
            }
        }
        expected_messages = [
            ('write', f"**Remaining Matches for {self.full_team_name}:** 3"),
            ('warning', f"**Possible Qualification:** Analysis result: error_val"),
            ('success', f"**Guaranteed Qualification:** Win **1** match(es) (irrespective of other results).")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

    def test_scenario9_exhaustive_guaranteed_wins_unexpected_type(self):
        analysis_method_used = "Exhaustive"
        analysis_data = {
            "qualification_path": {
                str(self.top_n): {
                    self.team_key: {
                        "possible": 1,
                        "guaranteed": "error_val",
                        "target_matches": 3
                    }
                }
            }
        }
        expected_messages = [
            ('write', f"**Remaining Matches for {self.full_team_name}:** 3"),
            ('success', f"**Possible Qualification:** Win **1** match(es) (with favorable results)."),
            ('warning', f"**Guaranteed Qualification:** Analysis result: error_val")
        ]
        result = get_qualification_path_messages(analysis_method_used, analysis_data, self.team_key, self.full_team_name, self.top_n)
        self.assertEqual(result, expected_messages)

if __name__ == '__main__':
    unittest.main()
