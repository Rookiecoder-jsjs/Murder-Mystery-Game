// Sidebar Component

import { Users, MessageSquare, Lightbulb } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Avatar } from '../common';
import './Sidebar.css';

export function Sidebar() {
  const { state } = useGame();

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <h3 className="sidebar-section-title">
          <Users size={14} />
          Characters
        </h3>
        <div className="sidebar-character-list">
          {state.characters.map((char) => (
            <div
              key={char.id}
              className={`sidebar-character ${
                state.player?.id === char.id ? 'is-player' : ''
              }`}
            >
              <Avatar name={char.name} size="md" />
              <div className="sidebar-character-info">
                <span className="sidebar-character-name">{char.name}</span>
                <span className="sidebar-character-identity">{char.public_identity}</span>
              </div>
              {state.player?.id === char.id && (
                <span className="sidebar-character-badge">You</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {state.accusationPoints > 0 && (
        <div className="sidebar-section">
          <h3 className="sidebar-section-title">
            <Lightbulb size={14} />
            Accusations
          </h3>
          <div className="sidebar-stat">
            <span className="sidebar-stat-value">{state.accusationPoints}</span>
            <span className="sidebar-stat-label">remaining</span>
          </div>
        </div>
      )}

      <div className="sidebar-section">
        <h3 className="sidebar-section-title">
          <MessageSquare size={14} />
          Discussion
        </h3>
        <div className="sidebar-stat">
          <span className="sidebar-stat-value">{state.currentDiscussionMessages.length}</span>
          <span className="sidebar-stat-label">messages</span>
        </div>
      </div>
    </aside>
  );
}
