// TypingIndicator — AI 回应生成中的占位提示
import './TypingIndicator.css';

interface TypingIndicatorProps {
  label?: string;
}

export function TypingIndicator({ label = '对方正在思考' }: TypingIndicatorProps) {
  return (
    <div className="typing-indicator" role="status">
      <span className="typing-label">{label}</span>
      <span className="typing-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}
