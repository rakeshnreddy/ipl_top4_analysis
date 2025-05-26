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
}

const ProbabilityChart: React.FC<ProbabilityChartProps> = ({ chartData, titleText }) => {
  const data: ChartData<'bar'> = {
    labels: chartData.map(d => team_short_names[d.teamKey] || d.teamKey),
    datasets: [
      {
        label: titleText,
        data: chartData.map(d => d.probability),
        backgroundColor: chartData.map(d => (team_styles[d.teamKey] as TeamStyle)?.bg || '#cccccc'),
        borderColor: chartData.map(d => (team_styles[d.teamKey] as TeamStyle)?.text || '#333333'),
        borderWidth: 1,
      },
    ],
  };

  const options: ChartOptions<'bar'> = {
    indexAxis: 'y' as const, // Horizontal bar chart
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        beginAtZero: true,
        max: 100, // Probabilities are 0-100
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
        display: false, // Legend can be hidden if title is clear
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
  };

  return <Bar options={options} data={data} />;
};

export default ProbabilityChart;
