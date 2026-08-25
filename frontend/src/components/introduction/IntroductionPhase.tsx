// Introduction Phase — 角色介绍与开场自白
import { useState } from 'react';
import { User, Play, ArrowRight } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Avatar, useToast } from '../common';
import './IntroductionPhase.css';

export function IntroductionPhase() {
  const { state, introduce, nextPhase } = useGame();
  const { notify } = useToast();
  const [customIntro, setCustomIntro] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);

  const hasResults = state.introductions.length > 0;

  const handleStartIntroduction = async () => {
    // 已有结果时不再重复触发（避免服务端重跑所有 AI 介绍）
    if (isSubmitting || hasResults) return;
    setIsSubmitting(true);
    try {
      await introduce(customIntro || undefined);
    } catch (err) {
      notify(err instanceof Error ? err.message : '自我介绍失败', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNextPhase = async () => {
    if (isAdvancing) return;
    setIsAdvancing(true);
    try {
      await nextPhase();
    } catch (err) {
      notify(err instanceof Error ? err.message : '进入下一阶段失败', 'error');
    } finally {
      setIsAdvancing(false);
    }
  };

  const defaultIntro = state.player
    ? `大家好，我是${state.player.name}，${state.player.public_identity}。`
    : '';

  return (
    <div className="introduction-phase">
      <div className="introduction-header">
        <div className="introduction-icon">
          <User size={24} />
        </div>
        <h2 className="introduction-title">自我介绍</h2>
        <p className="introduction-subtitle">
          每位角色都会介绍自己，留意每个人的说辞
        </p>
      </div>

      <Card variant="gold-border" className="introduction-player-card">
        <div className="introduction-player">
          <Avatar name={state.player?.name || '你'} size="xl" showBorder />
          <div className="introduction-player-details">
            <h3 className="introduction-player-name">{state.player?.name}</h3>
            <p className="introduction-player-identity">
              {state.player?.public_identity}
            </p>
            <p className="introduction-player-appearance">
              {state.player?.appearance}
            </p>
          </div>
        </div>
      </Card>

      {!hasResults && (
        <Card className="introduction-input-card">
          <h4 className="introduction-input-title">你的自我介绍</h4>
          <p className="introduction-input-hint">
            使用默认介绍，或写一段更符合你角色的开场白
          </p>
          <textarea
            className="introduction-textarea"
            value={customIntro || defaultIntro}
            onChange={(e) => setCustomIntro(e.target.value)}
            placeholder="输入你的自我介绍…"
            rows={4}
            maxLength={500}
          />
          <Button
            variant="primary"
            onClick={handleStartIntroduction}
            isLoading={isSubmitting}
            className="introduction-submit"
          >
            <Play size={16} />
            开始自我介绍
          </Button>
        </Card>
      )}

      {isSubmitting && (
        <Card className="introduction-waiting">
          <p>各位角色正在准备自我介绍，请稍候…</p>
        </Card>
      )}

      {hasResults && (
        <Card className="introduction-results">
          <h4 className="introduction-results-title">自我介绍</h4>
          {state.introductions.map((intro, index) => (
            <div
              key={`${intro.speaker}-${index}`}
              className={`introduction-result-item ${
                intro.speaker === state.player?.name ? 'is-player' : ''
              }`}
            >
              <span className="introduction-result-speaker">
                {intro.speaker}
              </span>
              <p className="introduction-result-message">{intro.message}</p>
            </div>
          ))}
        </Card>
      )}

      <div className="introduction-other-chars">
        <h4 className="introduction-other-title">其他角色</h4>
        <div className="introduction-other-grid">
          {state.characters
            .filter((c) => c.id !== state.player?.id)
            .map((char) => (
              <Card key={char.id} className="introduction-other-card">
                <Avatar name={char.name} size="lg" />
                <div className="introduction-other-info">
                  <span className="introduction-other-name">{char.name}</span>
                  <span className="introduction-other-identity">
                    {char.public_identity}
                  </span>
                </div>
              </Card>
            ))}
        </div>
      </div>

      {hasResults && (
        <Button
          variant="primary"
          size="lg"
          onClick={handleNextPhase}
          isLoading={isAdvancing}
          className="introduction-continue"
        >
          进入搜证阶段
          <ArrowRight size={16} />
        </Button>
      )}
    </div>
  );
}
