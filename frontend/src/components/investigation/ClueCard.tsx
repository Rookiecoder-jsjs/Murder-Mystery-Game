// Clue Card Component
import { Search, MessageSquare, FileText } from 'lucide-react';
import type { Clue } from '../../api/types';
import { Badge } from '../common';
import './ClueCard.css';

interface ClueCardProps {
  clue: Clue;
  onClick?: () => void;
}

const clueIcons = {
  physical: <Search size={16} />,
  testimony: <MessageSquare size={16} />,
  document: <FileText size={16} />,
};

export function ClueCard({ clue, onClick }: ClueCardProps) {
  return (
    <div
      className={`clue-card clue-card-${clue.type}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
    >
      <div className="clue-card-header">
        <div className="clue-card-type">
          {clueIcons[clue.type as keyof typeof clueIcons]}
          <span>{clue.type}</span>
        </div>
        <Badge
          variant={
            clue.type === 'physical'
              ? 'physical'
              : clue.type === 'testimony'
              ? 'testimony'
              : 'document'
          }
          size="sm"
        >
          {clue.type === 'physical' ? '物证' : clue.type === 'testimony' ? '证词' : '文书'}
        </Badge>
      </div>
      <p className="clue-card-content">{clue.content}</p>
      <div className="clue-card-footer">
        <span className="clue-card-holder">持有者: {clue.holder_name}</span>
      </div>
    </div>
  );
}
