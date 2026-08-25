// AccuseModal — 指认凶手弹窗（搜证/讨论阶段共用同一份实现）
import { useEffect, useState } from 'react';
import { AlertTriangle, Check } from 'lucide-react';
import type { CharacterInfo } from '../../api/types';
import { Modal } from './Modal';
import { Button } from './Button';
import { Card } from './Card';
import { Avatar } from './Avatar';
import './AccuseModal.css';

interface AccuseModalProps {
  isOpen: boolean;
  onClose: () => void;
  characters: CharacterInfo[];
  playerId?: string;
  accusationPoints: number;
  isAccusing: boolean;
  onConfirm: (characterName: string) => void;
}

export function AccuseModal({
  isOpen,
  onClose,
  characters,
  playerId,
  accusationPoints,
  isAccusing,
  onConfirm,
}: AccuseModalProps) {
  const [selected, setSelected] = useState<string | null>(null);

  // 关闭后清空选择
  useEffect(() => {
    if (!isOpen) setSelected(null);
  }, [isOpen]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="拘捕令" size="md">
      <div className="accuse-modal">
        <div className="accuse-warning">
          <AlertTriangle size={18} />
          <p>
            缉捕权限仅余 <strong>{accusationPoints}</strong> 次。
            签捕正确则好人胜利，错捕则真凶逍遥法外！
          </p>
        </div>

        <div className="accuse-suspects">
          <h4>在下列嫌犯中圈定一人：</h4>
          <div className="accuse-suspect-grid">
            {characters
              .filter((char) => char.id !== playerId)
              .map((char) => (
                <Card
                  key={char.id}
                  variant={selected === char.name ? 'gold-border' : 'default'}
                  className={`accuse-suspect-card ${
                    selected === char.name ? 'selected' : ''
                  }`}
                  onClick={() => setSelected(char.name)}
                  hoverable
                >
                  <Avatar
                    name={char.name}
                    size="md"
                    showBorder={selected === char.name}
                  />
                  <div className="accuse-suspect-info">
                    <span className="accuse-suspect-name">{char.name}</span>
                    <span className="accuse-suspect-identity">
                      {char.public_identity}
                    </span>
                  </div>
                  {selected === char.name && (
                    <div className="accuse-selected-badge">
                      <Check size={13} />
                    </div>
                  )}
                </Card>
              ))}
          </div>
        </div>

        <div className="accuse-actions">
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="danger"
            onClick={() => selected && onConfirm(selected)}
            disabled={!selected}
            isLoading={isAccusing}
          >
            签发拘捕令
          </Button>
        </div>
      </div>
    </Modal>
  );
}
