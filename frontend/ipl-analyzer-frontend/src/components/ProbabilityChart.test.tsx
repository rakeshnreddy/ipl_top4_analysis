/// <reference types="vitest/globals" />
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProbabilityChart from './ProbabilityChart';
import type { TeamStyle } from '../teamStyles';

// Mock teamStyles to ensure consistent snapshots and avoid issues if actual styles change
vi.mock('../teamStyles', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../teamStyles')>();
  return {
    ...actual,
    team_styles: {
      TeamA: { bg: '#ff0000', text: '#ffffff', accent: '#ff8800' } as TeamStyle,
      TeamB: { bg: '#00ff00', text: '#000000', accent: '#88ff00' } as TeamStyle,
    },
    team_short_names: {
      TeamA: 'TA',
      TeamB: 'TB',
    }
  };
});

// Mock ChartJS and its components as they are complex and not the focus of this unit test
vi.mock('react-chartjs-2', () => ({
  Bar: (props: any) => (
    <div data-testid="bar-chart-mock" aria-label={props['aria-label']} role={props['role']}>
      {/* You can add more details here if needed to check props passed to Bar */}
      <pre>{JSON.stringify(props.data, null, 2)}</pre>
      <pre>{JSON.stringify(props.options, null, 2)}</pre>
    </div>
  ),
}));

// Mock ChartJS registration (already done in component, but good for test isolation if needed)
vi.mock('chart.js', async (importOriginal) => {
 const actualChartJS = await importOriginal<typeof import('chart.js')>();
 return {
   ...actualChartJS,
   Chart: {
     ...actualChartJS.Chart,
     register: vi.fn(),
   },
   // Mock specific scales/elements if direct constructor calls were made in component
   // For this component, Chart.register handles it, so a simple register mock is enough.
 };
});


describe('ProbabilityChart Component', () => {
  const mockChartData = [
    { teamKey: 'TeamA', probability: 75.5 },
    { teamKey: 'TeamB', probability: 50.25 },
  ];

  const titleText = 'Test Chart Title';
  const ariaLabel = 'Test Chart Aria Label';

  it('Test 1: Renders correctly with mock data and matches snapshot', () => {
    const { container } = render(
      <ProbabilityChart chartData={mockChartData} titleText={titleText} ariaLabel={ariaLabel} />
    );

    // Check if the mock Bar chart is rendered
    expect(screen.getByTestId('bar-chart-mock')).toBeInTheDocument();
    
    // Check if title is used in options passed to Bar mock (indirectly checking title display)
    // This requires the mock to render the options.
    const optionsContent = screen.getByText(/"text": "Test Chart Title"/);
    expect(optionsContent).toBeInTheDocument();

    // Snapshot test
    // We are snapshotting the div container which includes our mock Bar chart
    expect(container.firstChild).toMatchSnapshot();
  });

  it('Test 2: Passes correct aria-label and role to the Bar chart', () => {
    render(
      <ProbabilityChart chartData={mockChartData} titleText={titleText} ariaLabel={ariaLabel} />
    );
    const barChartMock = screen.getByTestId('bar-chart-mock');
    expect(barChartMock).toHaveAttribute('aria-label', ariaLabel);
    expect(barChartMock).toHaveAttribute('role', 'img');
  });

  it('Test 3: Calculates chart height correctly', () => {
    const { container } = render(
      <ProbabilityChart chartData={mockChartData} titleText={titleText} ariaLabel={ariaLabel} />
    );
    // chartHeight = Math.max(300, chartData.length * 35);
    // chartData.length is 2, so 2 * 35 = 70. Math.max(300, 70) = 300.
    const expectedHeight = '300px';
    // The chart container is the firstChild of the render result
    expect(container.firstChild).toHaveStyle(`height: ${expectedHeight}`);
  });
  
  it('Test 4: Calculates chart height correctly with more data', () => {
    const moreMockData = [
      ...mockChartData,
      { teamKey: 'TeamC', probability: 20 },
      { teamKey: 'TeamD', probability: 30 },
      { teamKey: 'TeamE', probability: 40 },
      { teamKey: 'TeamF', probability: 50 },
      { teamKey: 'TeamG', probability: 60 },
      { teamKey: 'TeamH', probability: 70 },
      { teamKey: 'TeamI', probability: 80 }, // 9 teams
    ];
    // chartData.length is 9, so 9 * 35 = 315. Math.max(300, 315) = 315.
    const expectedHeight = '315px';
     const { container } = render(
      <ProbabilityChart chartData={moreMockData} titleText={titleText} ariaLabel={ariaLabel} />
    );
    expect(container.firstChild).toHaveStyle(`height: ${expectedHeight}`);
  });

});
