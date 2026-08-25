// Card — 基础卡片（金边变体用于高亮，无发光动画）
import React from 'react';
import './Card.css';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'gold-border';
  onClick?: () => void;
  hoverable?: boolean;
}

export function Card({
  children,
  className = '',
  variant = 'default',
  onClick,
  hoverable = false,
}: CardProps) {
  return (
    <div
      className={`card card-${variant} ${hoverable ? 'card-hoverable' : ''} ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}
