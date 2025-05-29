#!/bin/bash
# This script helps set up the development environment for the IPL Qualification Analyzer.

echo "Setting up development environment..."

# Set Node environment to development for the frontend
export NODE_ENV=development
echo "NODE_ENV set to $NODE_ENV"

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt..."
if pip install -r requirements.txt; then
    echo "Python dependencies installed successfully."
else
    echo "Failed to install Python dependencies. Please check errors."
    exit 1
fi

# Install frontend dependencies
echo "Installing frontend dependencies..."
if npm install --prefix frontend/ipl-analyzer-frontend; then
    echo "Frontend dependencies installed successfully."
else
    echo "Failed to install frontend dependencies. Please check errors."
    exit 1
fi

# Copy necessary data files to frontend public directory for development
# This ensures the frontend can access them via fetch requests
echo "Copying data files to frontend public directory..."
if [ -f "analysis_results.json" ] && [ -f "current_standings.json" ]; then
    cp analysis_results.json frontend/ipl-analyzer-frontend/public/
    cp current_standings.json frontend/ipl-analyzer-frontend/public/
    echo "Data files copied to frontend/ipl-analyzer-frontend/public/"
else
    echo "Warning: analysis_results.json or current_standings.json not found in the root directory. Frontend might not have all data."
fi

echo ""
echo "Development environment setup complete."
echo "You can now typically run the following in separate terminals:"
echo "1. For the Python backend/data generation (if needed for fresh data):"
echo "   - python generate_ipl_data.py"
echo "   - python precompute_analysis.py"
echo "2. To run the Streamlit app (optional, if using):"
echo "   - streamlit run ipl_analysis_app.py"
echo "3. For the React frontend development server:"
echo "   - npm run dev --prefix frontend/ipl-analyzer-frontend"
echo ""
echo "Remember to source this script if you want NODE_ENV to persist in your current shell:"
echo "source setup_dev_env.sh"
echo "Alternatively, just run it directly: ./setup_dev_env.sh (NODE_ENV will be set only for the script's execution)"
