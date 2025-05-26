import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DetailedTeamAnalysis from './DetailedTeamAnalysis'; // Adjust path as needed
// team_full_names is imported by the component, so we mock it at the module level
// import { team_full_names } from '../teamStyles';

// Mock team_full_names used by the component for teamFullName property
vi.mock('../teamStyles', () => ({
  team_full_names: {
    TeamA: "Team Alpha",
    TeamB: "Team Bravo",
    TeamC: "Team Charlie",
  },
  team_styles: {}, // Mock other exports if component uses them
  team_short_names: {},
}));


const mockAnalysisData = {
  metadata: { method_used: "Test Analysis", timestamp: new Date().toISOString() },
  analysis_data: {
    team_analysis: {
      "4": { // Top 4
        TeamA: { percentage: 90.50, results_df: { "Fixture1 (TeamX vs TeamY)": "TeamX wins", "Fixture2 (TeamZ vs TeamW)": "TeamZ wins" } },
        TeamB: { percentage: 80.00, results_df: { "Fixture3 (TeamP vs TeamQ)": "TeamP wins" } },
      },
      "2": { // Top 2
        TeamA: { percentage: 60.00, results_df: { "Fixture1 (TeamX vs TeamY)": "TeamY wins" } },
        TeamB: { percentage: 45.50, results_df: { "Fixture3 (TeamP vs TeamQ)": "TeamQ wins" } },
      }
    }
  }
};

describe('DetailedTeamAnalysis Component', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn<typeof globalThis, 'fetch'>>;

  beforeEach(() => {
    // Ensure fetch is mocked for each test
    fetchSpy = vi.spyOn(window, 'fetch');
  });

  afterEach(() => {
    vi.restoreAllMocks(); // Restores all mocks, including fetch
  });

  const setupFetchMock = (data: any, ok = true) => {
    fetchSpy.mockImplementation((url) => {
      if (typeof url === 'string' && url.endsWith('/analysis_results.json')) {
        return Promise.resolve({
          ok: ok,
          json: () => Promise.resolve(data),
          status: ok ? 200 : 500,
          statusText: ok ? "OK" : "Internal Server Error",
          headers: new Headers({ 'Content-Type': 'application/json' }),
          type: 'basic',
          url: url,
          redirected: false,
          clone: function() { return this; }, // Add clone method
          arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
          blob: () => Promise.resolve(new Blob()),
          formData: () => Promise.resolve(new FormData()),
          text: () => Promise.resolve(JSON.stringify(data)),
        } as Response);
      }
      // Fallback for any other fetch calls if necessary, or throw error
      return Promise.reject(new Error(`Unhandled fetch call: ${url}`));
    });
  };


  it('Test 1: Initial Render and Default Display', async () => {
    setupFetchMock(mockAnalysisData);
    render(<DetailedTeamAnalysis />);

    expect(screen.getByText(/loading detailed analysis.../i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/Team Alpha - Top 4 Analysis/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Chance to qualify for Top 4: 90.50%/i)).toBeInTheDocument();
    expect(screen.getByText("Fixture1 (TeamX vs TeamY)")).toBeInTheDocument();
    expect(screen.getByText("TeamX wins")).toBeInTheDocument();
  });

  it('Test 2: Team Selection Change', async () => {
    setupFetchMock(mockAnalysisData);
    render(<DetailedTeamAnalysis />);

    await waitFor(() => {
      expect(screen.getByText(/Team Alpha - Top 4 Analysis/i)).toBeInTheDocument();
    });
    
    const teamSelect = screen.getByLabelText(/Select Team:/i);
    fireEvent.change(teamSelect, { target: { value: 'TeamB' } });

    await waitFor(() => {
      expect(screen.getByText(/Team Bravo - Top 4 Analysis/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Chance to qualify for Top 4: 80.00%/i)).toBeInTheDocument();
    expect(screen.getByText("Fixture3 (TeamP vs TeamQ)")).toBeInTheDocument();
    expect(screen.getByText("TeamP wins")).toBeInTheDocument();
  });

  it('Test 3: Target Selection Change', async () => {
    setupFetchMock(mockAnalysisData);
    render(<DetailedTeamAnalysis />);

    await waitFor(() => {
      expect(screen.getByText(/Team Alpha - Top 4 Analysis/i)).toBeInTheDocument();
    });

    const top2Radio = screen.getByLabelText(/Top 2/i);
    fireEvent.click(top2Radio);

    await waitFor(() => {
      expect(screen.getByText(/Team Alpha - Top 2 Analysis/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Chance to qualify for Top 2: 60.00%/i)).toBeInTheDocument();
    expect(screen.getByText("Fixture1 (TeamX vs TeamY)")).toBeInTheDocument();
    expect(screen.getByText("TeamY wins")).toBeInTheDocument();
  });

  it('Test 4: Error State', async () => {
    // Specific setup for this test to simulate a network error
    fetchSpy.mockImplementation(() => Promise.reject(new TypeError('Network Error')));
    
    render(<DetailedTeamAnalysis />);

    await waitFor(() => {
      // Error message from component: `Failed to load analysis data. (${fetchError.message})`
      // Corrected regex to match the actual error message format
      expect(screen.getByText(/Failed to load analysis data. \(Network Error\)/i)).toBeInTheDocument();
    });
  });
});
