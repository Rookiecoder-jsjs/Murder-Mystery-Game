// Introduction Phase Component
import { useState } from 'react';
import { User, Play } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Avatar } from '../common';
import './IntroductionPhase.css';

export function IntroductionPhase() {
  const { state, introduce } = useGame();
  const [customIntro, setCustomIntro] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleStartIntroduction = async () => {
    setIsSubmitting(true);
    try {
      await introduce(customIntro || undefined);
    } finally {
      setIsSubmitting(false);
    }
  };

  const defaultIntro = state.player
    ? `大家好，我是${state.player.name}，${state.player.public_identity}。`
    : '';

  return (
    <div className="introduction-phase">
      <div className="introduction-header">
        <div className="introduction-icon">
          <User size={32} />
        </div>
        <h2 className="introduction-title">自我介绍阶段</h2>
        <p className="introduction-subtitle">
          每个人都将有机会介绍自己的角色
        </p>
      </div>

      <Card variant="gold-border" className="introduction-player-card">
        <div className="introduction-player">
          <Avatar name={state.player?.name || 'Player'} size="xl" showBorder />
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

      <Card className="introduction-input-card">
        <h4 className="introduction-input-title">你的自我介绍</h4>
        <p className="introduction-input-hint">
          使用默认自我介绍或输入自定义内容
        </p>
        <textarea
          className="introduction-textarea"
          value={customIntro || defaultIntro}
          onChange={(e) => setCustomIntro(e.target.value)}
          placeholder="输入你的自我介绍..."
          rows={4}
        />
        <Button
          variant="primary"
          size="lg"
          onClick={handleStartIntroduction}
          isLoading={isSubmitting}
          className="introduction-submit"
        >
          <Play size={18} />
          开始自我介绍
        </Button>
      </Card>

      <div className="introduction-other-chars">
        <h4 className="introduction-other-title">其他角色</h4>
        <div className="introduction-other-grid">
          {state.characters
            .filter((c) => c.id !== state.player?.id)
            .map((char) => (
              <Card key={char.id} variant="default" className="introduction-other-card">
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
    </div>
  );
}
