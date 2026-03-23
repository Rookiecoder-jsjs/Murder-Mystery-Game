// Phase Indicator Component

import React from 'react';
import { User, Search, MessageSquare, Vote, Eye } from 'lucide-react';
import type { GamePhase } from '../../api/types';
import './PhaseIndicator.css';

interface PhaseIndicatorProps {
  phase: GamePhase;
  round?: number;
  maxRounds?: number;
}

const phases: { key: GamePhase; label: string; icon: React.ReactNode }[] = [
  { key: 'introduction', label: '介绍', icon: <User size={14} /> },
  { key: 'investigation', label: '搜证', icon: <Search size={14} /> },
  { key: 'discussion', label: '讨论', icon: <MessageSquare size={14} /> },
  { key: 'voting', label: '投票', icon: <Vote size={14} /> },
  { key: 'reveal', label: '揭晓', icon: <Eye size={14} /> },
];

export function PhaseIndicator({ phase, round, maxRounds }: PhaseIndicatorProps) {
  const currentIndex = phases.findIndex((p) => p.key === phase);

  return (
    <div className="phase-indicator">
      {phases.map((p, index) => {
        const isActive = p.key === phase;
        const isPast = index < currentIndex;

        return (
          <React.Fragment key={p.key}>
            <div
              className={`phase-step ${isActive ? 'active' : ''} ${isPast ? 'past' : ''}`}
            >
              <div className="phase-icon">{p.icon}</div>
              <span className="phase-label">{p.label}</span>
            </div>
            {index < phases.length - 1 && (
              <div className={`phase-connector ${isPast ? 'past' : ''}`} />
            )}
          </React.Fragment>
        );
      })}
      {round !== undefined && maxRounds !== undefined && phase === 'discussion' && (
        <div className="phase-round">
          <span className="phase-round-label">回合</span>
          <span className="phase-round-value">
            {round}/{maxRounds}
          </span>
        </div>
      )}
    </div>
  );
}
