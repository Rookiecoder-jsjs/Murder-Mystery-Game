// Header Component
import { useGame } from '../../context/GameContext';
import { PhaseIndicator } from './PhaseIndicator';
import './Header.css';

export function Header() {
  const { state } = useGame();

  return (
    <header className="header">
      <div className="header-brand">
        <h1 className="header-title">
          <span className="header-title-accent">剧本</span>杀
        </h1>
        <span className="header-subtitle">Murder Mystery</span>
      </div>

      {state.gameId && (
        <div className="header-center">
          <PhaseIndicator
            phase={state.phase}
            round={state.round}
            maxRounds={state.maxRounds}
          />
        </div>
      )}

      <div className="header-info">
        {state.player && (
          <div className="header-player">
            <span className="header-player-label">Your Role</span>
            <span className="header-player-name">{state.player.name}</span>
          </div>
        )}
      </div>
    </header>
  );
}
