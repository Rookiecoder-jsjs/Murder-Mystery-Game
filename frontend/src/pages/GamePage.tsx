// Game Page - Main game interface
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../context/GameContext';
import { GameLayout } from '../components/layout';
import { IntroductionPhase } from '../components/introduction';
import { InvestigationPhase } from '../components/investigation';
import { DiscussionPhase } from '../components/discussion';
import { VotingPhase } from '../components/voting';
import { RevealPhase } from '../components/reveal';
import { LoadingSpinner } from '../components/common';
import './GamePage.css';

export function GamePage() {
  const navigate = useNavigate();
  const { state, refreshStatus, refreshClues } = useGame();

  useEffect(() => {
    if (!state.gameId) {
      navigate('/');
      return;
    }

    // Initial data load
    refreshStatus();
    refreshClues();

    // Set up polling based on phase
    const pollingInterval = state.phase === 'discussion' ? 3000 : 5000;
    const intervalId = setInterval(() => {
      refreshStatus();
      if (state.phase === 'investigation') {
        refreshClues();
      }
    }, pollingInterval);

    return () => clearInterval(intervalId);
  }, [state.gameId, state.phase, navigate, refreshStatus, refreshClues]);

  if (!state.gameId) {
    return (
      <div className="game-loading">
        <LoadingSpinner text="加载游戏中..." />
      </div>
    );
  }

  const renderPhase = () => {
    switch (state.phase) {
      case 'introduction':
        return <IntroductionPhase />;
      case 'investigation':
        return <InvestigationPhase />;
      case 'discussion':
        return <DiscussionPhase />;
      case 'voting':
        return <VotingPhase />;
      case 'reveal':
        return <RevealPhase />;
      default:
        return <IntroductionPhase />;
    }
  };

  return (
    <GameLayout>
      <div className="game-page">
        {renderPhase()}
      </div>
    </GameLayout>
  );
}
