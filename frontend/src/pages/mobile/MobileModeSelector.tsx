import type { GameMode } from '../../api/types';

export function MobileModeSelector({ value, onChange, disabled = false }: {
  value: GameMode; onChange: (value: GameMode) => void; disabled?: boolean;
}) {
  return <div className="mobile-mode-selector" role="group" aria-label="选择游玩模式">
    <button type="button" aria-pressed={value === 'quick'} disabled={disabled} onClick={() => onChange('quick')}>
      <strong>速推模式</strong><small>三轮调查与讨论</small>
    </button>
    <button type="button" aria-pressed={value === 'classic'} disabled={disabled} onClick={() => onChange('classic')}>
      <strong>经典模式</strong><small>自由调查与讨论</small>
    </button>
  </div>;
}
