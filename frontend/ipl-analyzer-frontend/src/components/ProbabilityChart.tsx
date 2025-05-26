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
} from 'chart.js';
import type { ChartOptions, ChartData } from 'chart.js'; // Types from chart.js

import { team_short_names, team_styles } from '../teamStyles'; // Values from teamStyles
import type { TeamStyle } from '../teamStyles'; // Types from teamStyles

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
        label: 'Probability', // Keep label simple for screen readers
        data: chartData.map(d => d.probability),
        backgroundColor: chartData.map(d => (team_styles[d.teamKey] as TeamStyle)?.bg || '#cccccc'),
        borderColor: chartData.map(d => (team_styles[d.teamKey] as TeamStyle)?.text || '#333333'),
        borderWidth: 1,
      },
    ],
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
          }
        }
      },
      y: {
        ticks: {
          autoSkip: false,
        },
      },
    },
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: true,
        text: titleText,
        font: {
          size: 16,
        }
      },
      tooltip: {
        callbacks: {
          label: function (context) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.x !== null) {
              label += context.parsed.x.toFixed(2) + '%';
            }
            return label;
          },
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
    <div style={{ height: `${chartHeight}px`, position: 'relative' }}>
      <Bar options={options} data={data} aria-label={ariaLabel} role="img" />
    </div>
  );
};

export default ProbabilityChart;
