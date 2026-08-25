// Avatar — 角色证件照瓦片（色板来自令牌，玩家态用朱红描边）
import type { CSSProperties } from 'react';
import './Avatar.css';

interface AvatarProps {
  name: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showBorder?: boolean;
  className?: string;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function getColorVar(name: string): string {
  const index = name
    .split('')
    .reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return `var(--avatar-c-${(index % 6) + 1})`;
}

export function Avatar({
  name,
  size = 'md',
  showBorder = false,
  className = '',
}: AvatarProps) {
  return (
    <div
      className={`avatar avatar-${size} ${showBorder ? 'avatar-border' : ''} ${className}`}
      style={{ '--avatar-bg': getColorVar(name) } as CSSProperties}
      title={name}
      aria-hidden="true"
    >
      <span className="avatar-initials">{getInitials(name)}</span>
    </div>
  );
}
