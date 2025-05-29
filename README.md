# IPL Qualification Probability Analyzer

## Overview

The IPL Qualification Probability Analyzer is a tool designed to analyze Indian Premier League (IPL) match data, simulate potential future scenarios, and predict team qualification probabilities for playoffs. It features a dynamic user interface with a warm-toned, glassmorphic design, supporting both light and dark modes.

The backend is powered by Python scripts that handle data extraction, processing, and analysis (including exhaustive and Monte Carlo simulations). The frontend is a modern React application built with Vite and TypeScript, providing an interactive experience for users to explore standings, team analysis, and simulation results.

## Features

*   **Current IPL Standings**: View the latest team standings.
*   **Detailed Team Analysis**: Explore detailed qualification scenarios for each team.
*   **Scenario Simulation**: Simulate outcomes of remaining matches to see their impact on standings.
*   **Probability Charts**: Visualize team qualification probabilities (Top 4, Top 2).
*   **Dynamic UI Theme**: User-selectable warm-toned theme with light and dark modes, featuring glassmorphism effects.
*   **Responsive Design**: UI adapts to different screen sizes.

## Tech Stack

*   **Backend & Analysis**: Python, Streamlit (for API/backend serving), Pandas
*   **Frontend**: React, Vite, TypeScript, Chart.js (via react-chartjs-2), Altair (for some charts in Streamlit app)
*   **Styling**: CSS with Custom Properties for dynamic theming.

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Setup Python Backend & Analysis Environment:**
    *   Ensure you have Python 3.8+ installed.
    *   It's recommended to create a virtual environment:
        ```bash
        python -m venv .venv
        source .venv/bin/activate  # On Windows: .venv\Scripts\activate
        ```
    *   Install Python dependencies:
        ```bash
        pip install -r requirements.txt
        ```

3.  **Setup Frontend Environment:**
    ```bash
    cd frontend/ipl-analyzer-frontend
    npm install
    cd ../.. 
    ```
    (Navigate back to the root directory after frontend setup)

## Running the Application

The application consists of a Python backend (Streamlit app) that also serves data, and a React frontend that consumes this data.

1.  **Generate/Update Data (if necessary):**
    *   The application relies on JSON data files (`current_standings.json`, `remaining_fixtures.json`, `analysis_results.json`).
    *   To update `current_standings.json` and `remaining_fixtures.json` from live sources (requires CricAPI key for `extract_table.py` or web scraping for `generate_ipl_data.py`):
        ```bash
        # Option 1: Using CricAPI (Update API_KEY in script)
        # python extract_table.py 
        
        # Option 2: Using ESPNCricinfo Scraper (Potentially less stable)
        python generate_ipl_data.py 
        ```
    *   To precompute analysis results (creates `analysis_results.json`):
        ```bash
        python precompute_analysis.py
        ```
    *   Note: The frontend expects these JSON files to be available in its `public` directory to be served by Vite during development, or copied to the build output. The Python scripts currently save them at the root. You may need to copy these files to `frontend/ipl-analyzer-frontend/public/` after generation for the React app to fetch them directly.

2.  **Run the Python Streamlit Application (Backend/API):**
    *   The Streamlit application (`ipl_analysis_app.py`) can serve as an interactive UI itself and also potentially as an API if the frontend is configured to fetch data from it (though current frontend setup seems to fetch static JSONs).
    ```bash
    streamlit run ipl_analysis_app.py
    ```
    This will typically run on `http://localhost:8501`.

3.  **Run the React Frontend Development Server:**
    ```bash
    cd frontend/ipl-analyzer-frontend
    npm run dev
    ```
    This will usually start the frontend on `http://localhost:5173` (or another port if 5173 is busy). The frontend fetches data from its `public` folder.

**Note on Data Flow for Frontend:**
The React frontend (`frontend/ipl-analyzer-frontend`) is configured to fetch `analysis_results.json` and `current_standings.json` from its `public` folder (via `import.meta.env.BASE_URL`). Ensure these JSON files are up-to-date and placed in `frontend/ipl-analyzer-frontend/public/` for the frontend to function correctly.

## Project Structure

```
.
├── .devcontainer/       # VS Code Dev Container configuration
├── .github/             # GitHub Actions workflows
├── frontend/
│   └── ipl-analyzer-frontend/ # React/Vite frontend application
├── extract_table.py     # Python script for fetching data via CricAPI
├── generate_ipl_data.py # Python script for scraping data from ESPNCricinfo
├── ipl_analysis_app.py  # Main Streamlit application for IPL analysis
├── ipl_analysis_app_mc.py # Streamlit app variant with Monte Carlo focus (may be deprecated/merged)
├── precompute_analysis.py # Python script for precomputing analysis results
├── requirements.txt     # Python dependencies
├── current_standings.json # Stores current IPL standings
├── remaining_fixtures.json # Stores remaining IPL match fixtures
└── analysis_results.json  # Stores precomputed analysis probabilities
```

## Quick Environment Setup

A helper script `setup_dev_env.sh` is provided to automate parts of the development setup.

To use it:
1.  Make sure the script is executable:
    ```bash
    chmod +x setup_dev_env.sh
    ```
2.  Run the script:
    ```bash
    ./setup_dev_env.sh
    ```
    Alternatively, to ensure `NODE_ENV` is set for your current shell session:
    ```bash
    source setup_dev_env.sh
    ```

This script will:
- Set `NODE_ENV=development` (for the script's execution context if run directly, or for the current shell if sourced).
- Install Python dependencies from `requirements.txt`.
- Install frontend dependencies using `npm install --prefix frontend/ipl-analyzer-frontend`.
- Copy essential data JSON files (`analysis_results.json`, `current_standings.json`) from the root directory to the `frontend/ipl-analyzer-frontend/public/` directory to make them available for the frontend development server.

After running the script, you can typically follow the instructions in the "Running the Application" section to start the different parts of the project, though some steps (like dependency installation) will already be complete.
