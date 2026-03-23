// Reveal Phase Component
import { Eye, Trophy, Skull, Home } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Badge } from '../common';
import './RevealPhase.css';

export function RevealPhase() {
  const { state, resetGame } = useGame();

  const isWinner = state.winner === 'good';
  const isKillerWin = state.winner === 'killer';

  return (
    <div className="reveal-phase">
      <div className="reveal-header">
        <div className={`reveal-icon ${isWinner ? 'reveal-icon-win' : isKillerWin ? 'reveal-icon-lose' : ''}`}>
          <Eye size={32} />
        </div>
        <h2 className="reveal-title">真相大白</h2>
        <div className="reveal-result">
          {isWinner ? (
            <Badge variant="gold" className="reveal-result-badge">
              <Trophy size={14} />
              好人大获全胜
            </Badge>
          ) : isKillerWin ? (
            <Badge variant="danger" className="reveal-result-badge">
              <Skull size={14} />
              凶手逃脱
            </Badge>
          ) : null}
        </div>
      </div>

      {state.revealInfo && (
        <div className="reveal-content">
          <Card className="reveal-story-card" variant="gold-border">
            <div className="reveal-section">
              <h3 className="reveal-section-title">{state.revealInfo.case_info.title}</h3>
              <p className="reveal-section-bg">{state.revealInfo.case_info.background}</p>
            </div>

            <div className="reveal-divider"></div>

            <div className="reveal-section">
              <h4 className="reveal-label">案件真相</h4>
              <div className="reveal-truth">
                <div className="reveal-truth-item">
                  <span className="reveal-truth-label">受害者</span>
                  <span className="reveal-truth-value">{state.revealInfo.case_info.victim}</span>
                </div>
                <div className="reveal-truth-item">
                  <span className="reveal-truth-label">凶手</span>
                  <span className="reveal-truth-value reveal-killer">
                    {state.revealInfo.case_info.true_killer}
                  </span>
                </div>
                <div className="reveal-truth-item">
                  <span className="reveal-truth-label">动机</span>
                  <span className="reveal-truth-value">{state.revealInfo.case_info.motive}</span>
                </div>
                <div className="reveal-truth-item">
                  <span className="reveal-truth-label">罪行</span>
                  <span className="reveal-truth-value">{state.revealInfo.case_info.crime}</span>
                </div>
              </div>
            </div>

            <div className="reveal-divider"></div>

            <div className="reveal-section">
              <h4 className="reveal-label">完整故事</h4>
              <p className="reveal-story-text">{state.revealInfo.story_content}</p>
            </div>
          </Card>
        </div>
      )}

      <div className="reveal-actions">
        <Button variant="primary" size="lg" onClick={resetGame}>
          <Home size={18} />
          返回首页
        </Button>
      </div>
    </div>
  );
}
