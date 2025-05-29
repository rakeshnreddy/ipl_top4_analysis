import React from 'react';
import { Bar } from 'react-chartjs-2';
import { // Values from chart.js
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'; // Values from chart.js
import type { ChartOptions, ChartData, TooltipItem } from 'chart.js'; // Types from chart.js

import { team_short_names, team_styles } from '../teamStyles'; // Import team_styles

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface ProbabilityChartProps {
  chartData: { teamKey: string; probability: number }[];
  titleText: string;
  ariaLabel: string;
}

const ProbabilityChart: React.FC<ProbabilityChartProps> = ({ chartData, titleText, ariaLabel }) => {
  const data: ChartData<'bar'> = {
    labels: chartData.map(d => team_short_names[d.teamKey] || d.teamKey),
    datasets: [
      {
        label: 'Probability',
        data: chartData.map(d => d.probability),
        backgroundColor: chartData.map(d => team_styles[d.teamKey]?.bg || '#CCCCCC'), // Use team color, fallback to gray
        borderColor: chartData.map(d => team_styles[d.teamKey]?.bg || '#CCCCCC'), // Use team color for border, fallback to gray
        borderWidth: 2,
        borderRadius: 6, // Rounded bars
        borderSkipped: false, // Border on all sides
      },
    ],
  };

  const tooltipLabelCallback = (context: TooltipItem<'bar'>): string => {
    let label = context.dataset.label || '';
    if (label) {
      label += ': ';
    }
    if (context.parsed.x !== null) {
      label += context.parsed.x.toFixed(2) + '%';
    }
    return label;
  };

  const options: ChartOptions<'bar'> = {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        beginAtZero: true,
        max: 100,
        title: {
          display: true,
          text: 'Probability (%)',
        },
        ticks: {
          callback: function(value) {
            return value + '%';
          },
          color: 'var(--text-color)' // Ensure this uses a theme-aware text color variable
        },
        grid: {
          display: false, // Remove X-axis grid lines
        }
      },
      y: {
        ticks: {
          autoSkip: false,
          color: 'var(--text-color)' // Ensure this uses a theme-aware text color variable
        },
        grid: {
          display: false, // Remove Y-axis grid lines
        },
      },
    }, // scales object ends
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: true,
        text: titleText,
        font: {
          family: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif", // Match body font
          size: 16,
        }
      },
      tooltip: {
        callbacks: {
          label: tooltipLabelCallback, // Assign the named function here
        },
      },
    },
    // Accessibility
    animation: false, // Disable animation for users sensitive to motion
    // The canvas element will get an aria-label from the Bar component props
  };

  // Height can be dynamic based on number of teams, or fixed
  const chartHeight = Math.max(300, chartData.length * 35); // Example dynamic height

  return (
    <div className="chart-container" style={{ height: `${chartHeight}px`, position: 'relative' }}>
      <Bar options={options} data={data} aria-label={ariaLabel} role="img" />
    </div>
  );
};

export default ProbabilityChart;
