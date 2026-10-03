// Reveal Phase — 真相揭晓（数据缺失时自愈式补取）
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, Trophy, Skull, Home } from 'lucide-react';
import { useGame } from '../../context/useGame';
import { Button, Card, Badge, LoadingSpinner, useToast } from '../common';
import './RevealPhase.css';

export function RevealPhase() {
  const navigate = useNavigate();
  const { state, resetGame, loadReveal, collectBallotAdvice } = useGame();
  const { notify } = useToast();
  const [adviceLoading, setAdviceLoading] = useState(false);
  const requestAdvice = async () => {
    setAdviceLoading(true);
    try { await collectBallotAdvice(); }
    catch (error) { notify(error instanceof Error ? error.message : '人物判断未完成，可稍后继续', 'error'); }
    finally { setAdviceLoading(false); }
  };

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
        <div className="reveal-seal-row">
          <span className="seal anim-seal" aria-hidden="true">
            落幕
          </span>
        </div>
      </div>

      <div className="reveal-content">
        {state.revealInfo.player_verdict?.target && <Card variant="gold-border">
          <h3>你的最终判断</h3>
          <p>你选择了 {state.revealInfo.player_verdict.target}，{state.revealInfo.player_verdict.correct ? '指认正确' : '指认错误'}。</p>
          <p>实际真凶：{state.revealInfo.case_info.true_killer_name}</p>
        </Card>}
        {!!state.revealInfo.deductions?.length && <Card>
          <h3>关键证据复盘</h3>
          {state.revealInfo.deductions.map((step, i) => <details className="reveal-deduction" key={i}>
            <summary>{step.conclusion}</summary>
            {step.evidence.map((evidence, j) => <div key={j}>
              <strong>{evidence.title || '定案证据'} · {evidence.discovered ? '本局已掌握' : '本局未发现'}</strong>
              <p>{evidence.quote}</p>
            </div>)}
          </details>)}
        </Card>}
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
                  <span className="seal seal--small reveal-killer-seal" aria-hidden="true">
                    凶
                  </span>
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

          <details className="reveal-section">
            <summary className="reveal-label">展开完整故事</summary>
            <p className="reveal-story-text">{state.revealInfo.story_content}</p>
          </details>
        </Card>
      </div>

      {!!state.revealInfo.votes?.length && (
        <Card>
          <h3>人物表决与理由</h3>
          <p>本局结果按你的最终选择判定。</p>
          {state.revealInfo.votes.map((ballot) => (
            <p key={ballot.voter}><strong>{ballot.voter} → {ballot.target}</strong>：{ballot.reason || '未提供理由'}</p>
          ))}
        </Card>
      )}
      {['available', 'running'].includes(state.revealInfo.advice_state || '') && <Card>
        <p>可以额外生成角色依据本局证据作出的判断，需要连接模型服务。</p>
        <Button onClick={requestAdvice} isLoading={adviceLoading}>查看人物判断</Button>
      </Card>}

      <div className="reveal-actions">
        <Button variant="primary" size="lg" onClick={handleBackHome}>
          <Home size={16} />
          返回首页
        </Button>
      </div>
    </div>
  );
}
