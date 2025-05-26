import './App.css';
import CurrentStandings from './components/CurrentStandings';
import DetailedTeamAnalysis from './components/DetailedTeamAnalysis';
import QualificationPath from './components/QualificationPath';
import ScenarioSimulation from './components/ScenarioSimulation';
import OverallProbabilities from './components/OverallProbabilities';

function App() {
  return (
    <div id="app-container">
      <header>
        <h1>IPL Qualification Analyzer</h1>
      </header>

      <section id="current-standings">
        <h2>Current Standings</h2>
        <CurrentStandings />
      </section>

      <section id="overall-probabilities">
        <h2>Overall Qualification Probabilities</h2>
        <OverallProbabilities />
      </section>

      <section id="team-analysis">
        <h2>Detailed Team Analysis</h2>
        <DetailedTeamAnalysis />
      </section>

      <section id="qualification-path">
        <h2>Qualification Path</h2>
        <QualificationPath />
      </section>

      <section id="scenario-simulation">
        <h2>Simulate One Scenario</h2>
        <ScenarioSimulation />
      </section>
    </div>
  );
}

export default App;
