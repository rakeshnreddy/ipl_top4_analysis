/// <reference types="vitest/globals" />
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App'; // Assuming App.tsx is in the same directory or path is adjusted

// Mock child components to simplify App testing and focus on App's own structure/styles
vi.mock('./components/CurrentStandings', () => ({
  default: () => <div data-testid="current-standings-mock">CurrentStandings Mock</div>,
}));
vi.mock('./components/OverallProbabilities', () => ({
  default: () => <div data-testid="overall-probabilities-mock">OverallProbabilities Mock</div>,
}));
vi.mock('./components/DetailedTeamAnalysis', () => ({
  default: () => <div data-testid="detailed-team-analysis-mock">DetailedTeamAnalysis Mock</div>,
}));
vi.mock('./components/QualificationPath', () => ({
  default: () => <div data-testid="qualification-path-mock">QualificationPath Mock</div>,
}));
vi.mock('./components/ScenarioSimulation', () => ({
  default: () => <div data-testid="scenario-simulation-mock">ScenarioSimulation Mock</div>,
}));

describe('App Component', () => {
  it('Test 1: Renders correctly and matches snapshot', () => {
    const { container } = render(<App />);
    
    // Check for main sections by aria-labelledby or heading text
    expect(screen.getByRole('heading', { name: /IPL Qualification Analyzer/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Current Standings/i })).toBeInTheDocument();
    expect(screen.getByTestId('current-standings-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Overall Qualification Probabilities/i })).toBeInTheDocument();
    expect(screen.getByTestId('overall-probabilities-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Detailed Team Analysis/i })).toBeInTheDocument();
    expect(screen.getByTestId('detailed-team-analysis-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Qualification Path/i })).toBeInTheDocument();
    expect(screen.getByTestId('qualification-path-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Simulate One Scenario/i })).toBeInTheDocument();
    expect(screen.getByTestId('scenario-simulation-mock')).toBeInTheDocument();
    
    // Snapshot test
    expect(container.firstChild).toMatchSnapshot();
  });

  it('Test 2: Footer renders correctly', () => {
    render(<App />);
    const year = new Date().getFullYear();
    expect(screen.getByText(`© ${year} IPL Analyzer. All rights reserved.`)).toBeInTheDocument();
    expect(screen.getByText('Data is for informational purposes only.')).toBeInTheDocument();
  });

  // Add more tests here if there's specific logic in App.tsx related to themes or styles
  // For example, if App.tsx had a theme toggler:
  // it('Test 3: Applies dark mode class when dark mode is active', () => {
  //   // Mock or set up a condition for dark mode
  //   // render(<App />);
  //   // expect(screen.getByTestId('app-container')).toHaveClass('dark-theme'); 
  //   // This depends on how dark mode is implemented.
  // });
});
