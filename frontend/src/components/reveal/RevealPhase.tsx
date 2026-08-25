// Reveal Phase — 真相揭晓（数据缺失时自愈式补取）
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, Trophy, Skull, Home } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Badge, LoadingSpinner } from '../common';
import './RevealPhase.css';

export function RevealPhase() {
  const navigate = useNavigate();
  const { state, resetGame, loadReveal } = useGame();

  // 直接进入揭晓（如轮询带过来的）而 revealInfo 缺失时，主动补取
  useEffect(() => {
    if (!state.revealInfo && state.gameId) {
      loadReveal();
    }
  }, [state.revealInfo, state.gameId, loadReveal]);

  const isWinner = state.winner === 'good';
  const isKillerWin = state.winner === 'killer';

  const handleBackHome = () => {
    resetGame();
    navigate('/');
  };

  if (!state.revealInfo) {
    return (
      <div className="reveal-phase">
        <div className="reveal-loading">
          <LoadingSpinner size="lg" text="正在揭晓真相…" />
        </div>
        <div className="reveal-actions">
          <Button variant="ghost" onClick={handleBackHome}>
            <Home size={16} />
            返回首页
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="reveal-phase">
      <div className="reveal-header">
        <div
          className={`reveal-icon ${
            isWinner ? 'reveal-icon-win' : isKillerWin ? 'reveal-icon-lose' : ''
          }`}
        >
          <Eye size={26} />
        </div>
        <h2 className="reveal-title">真相大白</h2>
        <div className="reveal-result">
          {isWinner ? (
            <Badge variant="gold" className="reveal-result-badge">
              <Trophy size={13} />
              好人大获全胜
            </Badge>
          ) : isKillerWin ? (
            <Badge variant="danger" className="reveal-result-badge">
              <Skull size={13} />
              凶手逃脱
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="reveal-content">
        <Card className="reveal-story-card" variant="gold-border">
          <div className="reveal-section">
            <h3 className="reveal-section-title">
              {state.revealInfo.case_info.title}
            </h3>
            <p className="reveal-section-bg">
              {state.revealInfo.case_info.background}
            </p>
          </div>

          <div className="reveal-divider" />

          <div className="reveal-section">
            <h4 className="reveal-label">案件真相</h4>
            <div className="reveal-truth">
              <div className="reveal-truth-item">
                <span className="reveal-truth-label">受害者</span>
                <span className="reveal-truth-value">
                  {state.revealInfo.case_info.victim}
                </span>
              </div>
              <div className="reveal-truth-item">
                <span className="reveal-truth-label">凶手</span>
                <span className="reveal-truth-value reveal-killer">
                  {state.revealInfo.case_info.true_killer_name ||
                    state.revealInfo.case_info.true_killer}
                </span>
              </div>
              <div className="reveal-truth-item">
                <span className="reveal-truth-label">动机</span>
                <span className="reveal-truth-value">
                  {state.revealInfo.case_info.motive}
                </span>
              </div>
              <div className="reveal-truth-item">
                <span className="reveal-truth-label">罪行</span>
                <span className="reveal-truth-value">
                  {state.revealInfo.case_info.crime}
                </span>
              </div>
            </div>
          </div>

          <div className="reveal-divider" />

          <div className="reveal-section">
            <h4 className="reveal-label">完整故事</h4>
            <p className="reveal-story-text">{state.revealInfo.story_content}</p>
          </div>
        </Card>
      </div>

      <div className="reveal-actions">
        <Button variant="primary" size="lg" onClick={handleBackHome}>
          <Home size={16} />
          返回首页
        </Button>
      </div>
    </div>
  );
}
