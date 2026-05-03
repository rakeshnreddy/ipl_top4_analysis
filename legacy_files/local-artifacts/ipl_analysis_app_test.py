import unittest
from unittest.mock import patch
import pandas as pd
import altair as alt

# Assuming ipl_analysis_app.py is in the same directory or accessible via PYTHONPATH
from ipl_analysis_app import (
    create_probability_chart,
    team_short_names,  # Imported for assertions
    team_styles,       # Imported for assertions and modification in one test
)

class TestCreateProbabilityChart(unittest.TestCase):

    def assertChartData(self, chart, expected_data_list, expected_title, expected_text_color=None, expected_text_font_size=12):
        """
        Helper method to check the data and properties within the Altair chart.
        """
        self.assertIsNotNone(chart, "Chart should not be None")
        self.assertIsInstance(chart, alt.HConcatChart, "Chart should be an Altair HConcatChart")
        self.assertEqual(len(chart.hconcat), 2, "Chart should have two horizontally concatenated parts (bars and text)")

        # Check chart title (Altair title might be a string directly)
        self.assertEqual(chart.title, expected_title, "Chart title does not match")

        # Data is expected to be on the top-level HConcatChart object
        # when sub-charts share the same data source.
        self.assertIsInstance(chart.data, pd.DataFrame, "Chart data should be a Pandas DataFrame")

        # Convert DataFrame to list of dicts for easier comparison
        actual_data_list = chart.data.to_dict(orient='records')

        self.assertEqual(len(actual_data_list), len(expected_data_list), "Number of data records does not match")

        # Sort both lists by 'Team' to ensure consistent comparison order
        sorted_actual = sorted(actual_data_list, key=lambda x: x['Team'])
        sorted_expected = sorted(expected_data_list, key=lambda x: x['Team'])

        for actual, expected in zip(sorted_actual, sorted_expected):
            self.assertEqual(actual['Team'], expected['Team'], f"Team name mismatch for {expected['Team']}")
            self.assertAlmostEqual(actual['Probability'], expected['Probability'], places=5, msg=f"Probability mismatch for {expected['Team']}")
            self.assertEqual(actual['BarColor'], expected['BarColor'], f"BarColor mismatch for {expected['Team']}")
            self.assertEqual(actual['ProbText'], expected['ProbText'], f"ProbText mismatch for {expected['Team']}")

        # Check text mark properties if expected_text_color is provided
        if expected_text_color:
            text_chart = chart.hconcat[1] # Get the second part for text mark properties
            self.assertEqual(text_chart.mark.type, "text", "Text chart mark type should be 'text'")
            # Access the color value from its dictionary representation for robustness
            actual_text_color = text_chart.encoding.color.to_dict().get('value')
            self.assertEqual(actual_text_color, expected_text_color,
                             f"Text mark color mismatch. Expected: {expected_text_color}, Got: {actual_text_color} (from to_dict())")
            self.assertEqual(text_chart.mark.fontSize, expected_text_font_size, "Text mark font size mismatch")

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_empty_data_dict(self, mock_get_option):
        chart = create_probability_chart({})
        self.assertIsNone(chart)

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_valid_data_single_team(self, mock_get_option):
        data_dict = {"Kolkata": {"Top 4 Probability": 75.5}}
        chart = create_probability_chart(data_dict)

        expected_chart_data = [{
            "Team": "KKR",
            "Probability": 0.755,
            "BarColor": team_styles["Kolkata"]["bg"],
            "ProbText": "75.5000%"
        }]
        self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#333333")

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_invalid_probability_value_string(self, mock_get_option):
        data_dict = {"Chennai": {"Top 4 Probability": "not_a_number"}}
        chart = create_probability_chart(data_dict)

        expected_chart_data = [{
            "Team": "CSK",
            "Probability": 0.0, # Default due to conversion error
            "BarColor": team_styles["Chennai"]["bg"],
            "ProbText": "0.0000%"
        }]
        self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#333333")

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_missing_probability_key(self, mock_get_option):
        data_dict = {"Mumbai": {}} # 'Top 4 Probability' is missing
        chart = create_probability_chart(data_dict)

        expected_chart_data = [{
            "Team": "MI",
            "Probability": 0.0, # Default from stats.get(prob_column, 0.0)
            "BarColor": team_styles["Mumbai"]["bg"],
            "ProbText": "0.0000%"
        }]
        self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#333333")

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_probability_value_none(self, mock_get_option):
        data_dict = {"Delhi": {"Top 4 Probability": None}}
        chart = create_probability_chart(data_dict)

        expected_chart_data = [{
            "Team": "DC",
            "Probability": 0.0, # Caught by except: prob = 0.0
            "BarColor": team_styles["Delhi"]["bg"],
            "ProbText": "0.0000%"
        }]
        self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#333333")

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_team_key_not_in_short_names_or_styles(self, mock_get_option):
        data_dict = {"UnknownTeam": {"Top 4 Probability": 50.0}}
        chart = create_probability_chart(data_dict)

        expected_chart_data = [{
            "Team": "UnknownTeam", # Fallback to team_key
            "Probability": 0.50,
            "BarColor": "#808080", # Default color
            "ProbText": "50.0000%"
        }]
        self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#333333")

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_team_key_in_short_names_not_in_styles(self, mock_get_option):
        original_bangalore_style = team_styles.pop("Bangalore", None)
        try:
            data_dict = {"Bangalore": {"Top 4 Probability": 25.0}} # Bangalore is in team_short_names
            chart = create_probability_chart(data_dict)

            expected_chart_data = [{
                "Team": "RCB", # From team_short_names
                "Probability": 0.25,
                "BarColor": "#808080", # Default color because style was removed
                "ProbText": "25.0000%"
            }]
            self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#333333")
        finally:
            if original_bangalore_style: # Restore
                team_styles["Bangalore"] = original_bangalore_style

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_team_style_defined_but_missing_bg_key(self, mock_get_option):
        # This tests if the code would break if a team_style entry was malformed (missing 'bg')
        original_rajasthan_style = team_styles.get("Rajasthan")
        team_styles["Rajasthan"] = {"text_only": "#000000"} # Malformed: No 'bg' key

        data_dict = {"Rajasthan": {"Top 4 Probability": 30.0}}

        # Expect a KeyError because team_styles.get() finds "Rajasthan", returns the malformed dict,
        # and then ["bg"] access fails.
        with self.assertRaises(KeyError) as context:
            create_probability_chart(data_dict)
        self.assertTrue('bg' in str(context.exception).lower(), "KeyError for 'bg' was not raised as expected.")

        # Restore original style
        if original_rajasthan_style:
            team_styles["Rajasthan"] = original_rajasthan_style
        else: # Should not happen with current data
            if "Rajasthan" in team_styles: del team_styles["Rajasthan"]

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_different_prob_column(self, mock_get_option):
        data_dict = {"Rajasthan": {"Top 2 Probability": 90.0}}
        chart = create_probability_chart(data_dict, prob_column="Top 2 Probability")

        expected_chart_data = [{
            "Team": "RR",
            "Probability": 0.90,
            "BarColor": team_styles["Rajasthan"]["bg"],
            "ProbText": "90.0000%"
        }]
        self.assertChartData(chart, expected_chart_data, "Top 2 Probability Chances", expected_text_color="#333333")

    @patch('ipl_analysis_app.st.get_option', return_value='dark') # Test with dark theme
    def test_multiple_teams_and_dark_theme_text_color(self, mock_get_option):
        data_dict = {
            "Kolkata": {"Top 4 Probability": 75.5},
            "Chennai": {"Top 4 Probability": "bad_value"},
            "UnknownTeam": {"Top 4 Probability": 10.0}
        }
        chart = create_probability_chart(data_dict)

        expected_chart_data = [
            {
                "Team": "KKR", "Probability": 0.755,
                "BarColor": team_styles["Kolkata"]["bg"], "ProbText": "75.5000%"
            },
            {
                "Team": "CSK", "Probability": 0.0,
                "BarColor": team_styles["Chennai"]["bg"], "ProbText": "0.0000%"
            },
            {
                "Team": "UnknownTeam", "Probability": 0.10,
                "BarColor": "#808080", "ProbText": "10.0000%"
            }
        ]
        self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#FFFFFF")

    @patch('ipl_analysis_app.st.get_option', return_value='light')
    def test_probability_zero_and_one_hundred(self, mock_get_option):
        data_dict = {
            "Punjab": {"Top 4 Probability": 0},
            "Gujarat": {"Top 4 Probability": 100.0}
        }
        chart = create_probability_chart(data_dict)

        expected_chart_data = [
            {
                "Team": "PBKS", "Probability": 0.0,
                "BarColor": team_styles["Punjab"]["bg"], "ProbText": "0.0000%"
            },
            {
                "Team": "GT", "Probability": 1.0, # prob / 100.0
                "BarColor": team_styles["Gujarat"]["bg"], "ProbText": "100.0000%"
            }
        ]
        self.assertChartData(chart, expected_chart_data, "Top 4 Probability Chances", expected_text_color="#333333")

if __name__ == '__main__':
    unittest.main()