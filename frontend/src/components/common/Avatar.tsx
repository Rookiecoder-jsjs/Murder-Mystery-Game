// Avatar — 角色头像（色板来自令牌，选中态用暗金描边）
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
      style={{ backgroundColor: getColorVar(name) }}
      title={name}
      aria-hidden="true"
    >
      <span className="avatar-initials">{getInitials(name)}</span>
    </div>
  );
}
