// Header — 64px：品牌 + 阶段指示 + 玩家身份
import { Menu } from 'lucide-react';
import { useGame } from '../../context/useGame';
import { PhaseIndicator } from './PhaseIndicator';
import './Header.css';

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { state } = useGame();

  return (
    <header className="header">
      <div className="header-left">
        <button
          className="header-menu-btn"
          onClick={onMenuClick}
          aria-label="打开角色列表"
        >
          <Menu size={18} />
        </button>
        <div className="header-brand">
          <h1 className="header-title font-display">剧本杀</h1>
          {state.topic && (
            <span className="header-topic" title={state.topic}>
              {state.topic}
            </span>
          )}
        </div>
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
            <span className="header-player-label">你的角色</span>
            <span className="header-player-name">{state.player.name}</span>
          </div>
        )}
      </div>
    </header>
  );
}
