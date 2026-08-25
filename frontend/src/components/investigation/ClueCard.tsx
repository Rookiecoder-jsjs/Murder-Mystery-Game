// Clue Card — 线索卡片（新发现的线索带徽标）
import { Search, MessageSquare, FileText } from 'lucide-react';
import type { Clue } from '../../api/types';
import { Badge } from '../common';
import './ClueCard.css';

interface ClueCardProps {
  clue: Clue;
  isNew?: boolean;
  onClick?: () => void;
}

const clueIcons = {
  physical: <Search size={15} />,
  testimony: <MessageSquare size={15} />,
  document: <FileText size={15} />,
};

const clueLabels = {
  physical: '物证',
  testimony: '证词',
  document: '文书',
};

export function ClueCard({ clue, isNew = false, onClick }: ClueCardProps) {
  const label = clueLabels[clue.type] ?? clue.type;

  return (
    <div
      className={`clue-card clue-card-${clue.type} ${isNew ? 'clue-card-new' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="clue-card-header">
        <div className="clue-card-type">
          {clueIcons[clue.type as keyof typeof clueIcons]}
          <span>{label}</span>
        </div>
        {isNew && <Badge variant="gold" size="sm">新发现</Badge>}
      </div>
      <p className="clue-card-content">{clue.content}</p>
      <div className="clue-card-footer">
        <span className="clue-card-holder">持有者：{clue.holder_name}</span>
      </div>
    </div>
  );
}
