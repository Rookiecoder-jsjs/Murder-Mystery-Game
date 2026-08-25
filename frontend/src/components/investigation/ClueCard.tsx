// Clue Card — 证物拍立得（编号章；新发现盖朱红「新」字章）
import { Search, MessageSquare, FileText } from 'lucide-react';
import type { Clue } from '../../api/types';
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
        {isNew ? (
          <span className="stamp stamp--seal">新</span>
        ) : (
          <span className="stamp clue-card-id">
            C-{clue.id.split('-').pop()?.slice(-4) ?? '0000'}
          </span>
        )}
      </div>
      <p className="clue-card-content">{clue.content}</p>
      <div className="clue-card-footer">
        <span className="clue-card-holder">持有者：{clue.holder_name}</span>
      </div>
    </div>
  );
}
