import React from 'react';
import './App.css';
import ThemeToggle from './components/ThemeToggle'; 
import PaletteSwitcher from './components/PaletteSwitcher'; // Add this
import ThemeSwitcher from './components/ThemeSwitcher/ThemeSwitcher'; // Import the new ThemeSwitcher
import GlassCard from './components/GlassCard'; 
import CurrentStandings from './components/CurrentStandings';
import OverallProbabilities from './components/OverallProbabilities';
import DetailedTeamAnalysis from './components/DetailedTeamAnalysis';
import QualificationPath from './components/QualificationPath';
import ScenarioSimulation from './components/ScenarioSimulation';

const App: React.FC = () => {
  console.log('App.tsx - BASE_URL:', import.meta.env.BASE_URL);
  return (
    <div id="app-container">
      <header>
        <h1>IPL Qualification Analyzer</h1>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <ThemeToggle />
          <PaletteSwitcher />
          <ThemeSwitcher /> {/* Add the new ThemeSwitcher here */}
        </div>
      </header>

      <section id="current-standings" aria-labelledby="current-standings-heading">
        <GlassCard>
          <h2 id="current-standings-heading">Current Standings</h2>
          <CurrentStandings />
        </GlassCard>
      </section>

      <section id="overall-probabilities" aria-labelledby="overall-probabilities-heading">
        <GlassCard>
          <h2 id="overall-probabilities-heading">Overall Qualification Probabilities</h2>
          <OverallProbabilities />
        </GlassCard>
      </section>

      <section id="team-analysis" aria-labelledby="team-analysis-heading">
        <GlassCard>
          <h2 id="team-analysis-heading">Detailed Team Analysis</h2>
          <DetailedTeamAnalysis />
        </GlassCard>
      </section>

      <section id="qualification-path" aria-labelledby="qualification-path-heading">
        <GlassCard>
          <h2 id="qualification-path-heading">Qualification Path</h2>
          <QualificationPath />
        </GlassCard>
      </section>

      <section id="scenario-simulation" aria-labelledby="scenario-simulation-heading">
        <GlassCard>
          <h2 id="scenario-simulation-heading">Simulate One Scenario</h2>
          <ScenarioSimulation />
        </GlassCard>
      </section>

      <footer>
        <p>&copy; {new Date().getFullYear()} IPL Analyzer. All rights reserved.</p>
        <p>Data is for informational purposes only.</p>
      </footer>
    </div>
  );
};

export default App;
