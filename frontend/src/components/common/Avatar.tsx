// Avatar Component
import './Avatar.css';

interface AvatarProps {
  name: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  imageUrl?: string;
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

function getColorFromName(name: string): string {
  const colors = [
    '#8B1538', // burgundy
    '#D4AF37', // gold
    '#4A90D9', // blue
    '#2D8B4E', // green
    '#8B5CF6', // purple
    '#C9A227', // amber
  ];
  const index = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[index % colors.length];
}

export function Avatar({
  name,
  size = 'md',
  imageUrl,
  showBorder = false,
  className = '',
}: AvatarProps) {
  const initials = getInitials(name);
  const bgColor = getColorFromName(name);

  return (
    <div
      className={`avatar avatar-${size} ${showBorder ? 'avatar-border' : ''} ${className}`}
      style={{ backgroundColor: imageUrl ? 'transparent' : bgColor }}
      title={name}
    >
      {imageUrl ? (
        <img src={imageUrl} alt={name} className="avatar-image" />
      ) : (
        <span className="avatar-initials">{initials}</span>
      )}
    </div>
  );
}
