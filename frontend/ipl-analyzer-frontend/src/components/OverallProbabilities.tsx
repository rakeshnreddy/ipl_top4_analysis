import React, { useEffect, useState } from 'react';
import ProbabilityChart from './ProbabilityChart'; // Ensure this path is correct

interface TeamProbabilities {
  'Top 4 Probability': number;
  'Top 2 Probability': number;
  // Add other probability keys if they exist, e.g., 'Win Title Probability'
}

interface OverallProbabilitiesData {
  [key: string]: TeamProbabilities; // Team key (e.g., "Chennai")
}

interface AnalysisMetadata {
  method_used: string;
  timestamp: string; // ISO string format
}

interface FetchedAnalysisData {
  metadata: AnalysisMetadata;
  analysis_data: {
    overall_probabilities: OverallProbabilitiesData;
    // other potential keys: team_analysis, qualification_path
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
    setLoading(true);
    fetch('/analysis_results.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data: FetchedAnalysisData) => {
        if (!data.analysis_data || !data.analysis_data.overall_probabilities) {
          throw new Error("Overall probabilities data is missing or malformed in the response.");
        }
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
        setError(null); // Clear previous errors
      })
      .catch((fetchError) => {
        console.error("Failed to load analysis results:", fetchError);
        setError(`Failed to load overall probabilities data. (${fetchError.message})`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <p role="status" aria-live="polite">Loading overall probabilities...</p>;
  }

  if (error) {
    return <p role="alert" aria-live="assertive">{error}</p>; // Style via global CSS
  }

  if (top4Data.length === 0 && top2Data.length === 0) {
    return <p>No overall probability data available at the moment.</p>
  }

  return (
    <div>
      {metadata && (
        <div className="metadata mb-2 glassy-panel"> {/* Added glassy-panel */}
          <p>Analysis Method: {metadata.method_used}</p>
          <p>Last Updated: {new Date(metadata.timestamp).toLocaleString()}</p>
        </div>
      )}
      <div className="charts-container" style={{ display: 'flex', flexDirection: 'row', gap: '20px', flexWrap: 'wrap' }}>
        {top4Data.length > 0 ? (
          <div className="chart-wrapper glassy-panel" style={{ flex: 1, minWidth: '300px', padding: '10px' }}> {/* Added glassy-panel */}
            <ProbabilityChart 
              chartData={top4Data} 
              titleText="Top 4 Qualification Probability" 
              ariaLabel="Bar chart showing Top 4 qualification probabilities for IPL teams"
            />
          </div>
        ) : (
          <p className="glassy-panel" style={{ flex: 1, minWidth: '300px' }}>No Top 4 probability data available.</p>
        )}
        {top2Data.length > 0 ? (
          <div className="chart-wrapper glassy-panel" style={{ flex: 1, minWidth: '300px', padding: '10px' }}> {/* Added glassy-panel */}
            <ProbabilityChart 
              chartData={top2Data} 
              titleText="Top 2 Qualification Probability"
              ariaLabel="Bar chart showing Top 2 qualification probabilities for IPL teams"
            />
          </div>
        ) : (
          <p className="glassy-panel" style={{ flex: 1, minWidth: '300px' }}>No Top 2 probability data available.</p>
        )}
      </div>
    </div>
  );
};

export default OverallProbabilities;
