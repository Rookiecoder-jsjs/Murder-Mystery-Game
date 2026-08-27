// Sidebar — 桌面端固定栏；≤768px 由 GameLayout 变为抽屉（不再整体消失）

import { Users, MessageSquare, Lightbulb, X } from 'lucide-react';
import { useGame } from '../../context/useGame';
import { Avatar, Badge } from '../common';
import './Sidebar.css';

interface SidebarProps {
  drawerOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ drawerOpen, onClose }: SidebarProps) {
  const { state } = useGame();

  return (
    <aside className={`sidebar ${drawerOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-drawer-header">
        <span className="sidebar-drawer-title">案件信息</span>
        <button className="sidebar-close" onClick={onClose} aria-label="关闭侧边栏">
          <X size={16} />
        </button>
      </div>

      <div className="sidebar-section">
        <h3 className="sidebar-section-title">
          <Users size={14} />
          出场角色
        </h3>
        <div className="sidebar-character-list">
          {state.characters.map((char) => {
            const isPlayer = state.player?.id === char.id;
            return (
              <div
                key={char.id}
                className={`sidebar-character ${isPlayer ? 'is-player' : ''}`}
              >
                <Avatar name={char.name} imageUrl={char.portrait_url} size="md" />
                <div className="sidebar-character-info">
                  <span className="sidebar-character-name">{char.name}</span>
                  <span className="sidebar-character-identity">
                    {char.public_identity}
                  </span>
                </div>
                {isPlayer && <Badge variant="gold" size="sm">你</Badge>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="sidebar-section">
        <h3 className="sidebar-section-title">
          <Lightbulb size={14} />
          指控机会
        </h3>
        <div className="sidebar-stat">
          <span className="sidebar-stat-value">{state.accusationPoints}</span>
          <span className="sidebar-stat-label">剩余次数</span>
        </div>
      </div>

      <div className="sidebar-section">
        <h3 className="sidebar-section-title">
          <MessageSquare size={14} />
          讨论
        </h3>
        <div className="sidebar-stat">
          <span className="sidebar-stat-value">
            {state.currentDiscussionMessages.length}
          </span>
          <span className="sidebar-stat-label">条发言</span>
        </div>
      </div>
    </aside>
  );
}
