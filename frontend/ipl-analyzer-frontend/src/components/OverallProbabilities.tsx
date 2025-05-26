import React, { useEffect, useState } from 'react';
import ProbabilityChart from './ProbabilityChart';

interface TeamProbabilities {
  'Top 4 Probability': number;
  'Top 2 Probability': number;
}

interface OverallProbabilitiesData {
  [key: string]: TeamProbabilities;
}

interface AnalysisMetadata {
  method_used: string;
  timestamp: string;
}

interface FetchedAnalysisData {
  metadata: AnalysisMetadata;
  analysis_data: {
    overall_probabilities: OverallProbabilitiesData;
  };
}

interface ChartReadyData {
  teamKey: string;
  probability: number;
}

const OverallProbabilities: React.FC = () => {
  const [top4Data, setTop4Data] = useState<ChartReadyData[]>([]);
  const [top2Data, setTop2Data] = useState<ChartReadyData[]>([]);
  const [metadata, setMetadata] = useState<AnalysisMetadata | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/analysis_results.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data: FetchedAnalysisData) => {
        setMetadata(data.metadata);
        const overallProbs = data.analysis_data.overall_probabilities;

        const processedTop4 = Object.entries(overallProbs)
          .map(([teamKey, probs]) => ({
            teamKey,
            probability: probs['Top 4 Probability'] || 0,
          }))
          .sort((a, b) => b.probability - a.probability);

        const processedTop2 = Object.entries(overallProbs)
          .map(([teamKey, probs]) => ({
            teamKey,
            probability: probs['Top 2 Probability'] || 0,
          }))
          .sort((a, b) => b.probability - a.probability);

        setTop4Data(processedTop4);
        setTop2Data(processedTop2);
        setLoading(false);
      })
      .catch((fetchError) => {
        console.error("Failed to load analysis results:", fetchError);
        setError(`Failed to load analysis data. ${fetchError.message}`);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <p>Loading overall probabilities...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      {metadata && (
        <div style={{ marginBottom: '15px', fontSize: '0.9em', color: '#555' }}>
          <p>Analysis Method: {metadata.method_used}</p>
          <p>Last Updated: {new Date(metadata.timestamp).toLocaleString()}</p>
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'row', gap: '20px' }}>
        <div style={{ flex: 1, height: '400px' /* Adjust height as needed */ }}>
          {top4Data.length > 0 ? (
            <ProbabilityChart chartData={top4Data} titleText="Top 4 Qualification Probability" />
          ) : (
            <p>No Top 4 probability data available.</p>
          )}
        </div>
        <div style={{ flex: 1, height: '400px' /* Adjust height as needed */ }}>
          {top2Data.length > 0 ? (
            <ProbabilityChart chartData={top2Data} titleText="Top 2 Qualification Probability" />
          ) : (
            <p>No Top 2 probability data available.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default OverallProbabilities;
