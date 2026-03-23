// Investigation Phase Component
import { useState } from 'react';
import { Search, Eye, MessageSquare, AlertTriangle, Check } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Badge, Modal, Avatar } from '../common';
import { ClueCard } from './ClueCard';
import './InvestigationPhase.css';

export function InvestigationPhase() {
  const { state, nextPhase, accuse } = useGame();
  const [selectedClue, setSelectedClue] = useState<string | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [showAccuseModal, setShowAccuseModal] = useState(false);
  const [selectedSuspect, setSelectedSuspect] = useState<string | null>(null);
  const [isAccusing, setIsAccusing] = useState(false);

  const handleTransitionToDiscussion = async () => {
    setIsTransitioning(true);
    try {
      await nextPhase();
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleAccuse = async () => {
    if (!selectedSuspect) return;
    setIsAccusing(true);
    try {
      await accuse(selectedSuspect);
      setShowAccuseModal(false);
    } catch (err) {
      console.error('Accuse failed:', err);
    } finally {
      setIsAccusing(false);
    }
  };

  const allClues = [...state.clues, ...state.scenePublicClues];
  const physicalClues = allClues.filter((c) => c.type === 'physical');
  const testimonyClues = allClues.filter((c) => c.type === 'testimony');
  const documentClues = allClues.filter((c) => c.type === 'document');

  // Get all characters including player for accusation display
  const allCharactersForDisplay = state.characters;

  return (
    <div className="investigation-phase">
      <div className="investigation-header">
        <div className="investigation-icon">
          <Search size={32} />
        </div>
        <h2 className="investigation-title">搜证阶段</h2>
        <p className="investigation-subtitle">
          调查线索，发现真相
        </p>
      </div>

      <div className="investigation-actions">
        {state.accusationPoints > 0 && (
          <Button
            variant="danger"
            onClick={() => setShowAccuseModal(true)}
            className="investigation-action"
          >
            <AlertTriangle size={16} />
            指认凶手 ({state.accusationPoints}次)
          </Button>
        )}
        <Button
          variant="primary"
          onClick={handleTransitionToDiscussion}
          isLoading={isTransitioning}
          className="investigation-action"
        >
          <MessageSquare size={16} />
          进入讨论
        </Button>
      </div>

      <div className="investigation-content">
        <Card className="investigation-clues-card">
          <div className="investigation-clues-header">
            <h3>
              <Eye size={18} />
              你的线索
            </h3>
            <Badge variant="gold">{state.clues.length} 条</Badge>
          </div>

          {state.clues.length === 0 ? (
            <div className="investigation-empty">
              <Search size={48} />
              <p>暂无线索</p>
              <span>点击刷新按钮获取新线索</span>
            </div>
          ) : (
            <div className="investigation-clues-grid">
              {state.clues.map((clue) => (
                <ClueCard
                  key={clue.id}
                  clue={clue}
                  onClick={() => setSelectedClue(clue.id)}
                />
              ))}
            </div>
          )}
        </Card>

        {state.scenePublicClues.length > 0 && (
          <Card className="investigation-scene-card">
            <div className="investigation-clues-header">
              <h3>
                <Eye size={18} />
                公开线索
              </h3>
              <Badge variant="info">{state.scenePublicClues.length} 条</Badge>
            </div>
            <div className="investigation-clues-grid">
              {state.scenePublicClues.map((clue) => (
                <ClueCard
                  key={clue.id}
                  clue={clue}
                  onClick={() => setSelectedClue(clue.id)}
                />
              ))}
            </div>
          </Card>
        )}

        <div className="investigation-categories">
          <Card className="investigation-category">
            <div className="investigation-category-header">
              <Badge variant="physical">物证</Badge>
              <span className="investigation-category-count">
                {physicalClues.length} 条
              </span>
            </div>
            <p className="investigation-category-desc">
              实体证据，可通过搜证获得
            </p>
          </Card>

          <Card className="investigation-category">
            <div className="investigation-category-header">
              <Badge variant="testimony">证词</Badge>
              <span className="investigation-category-count">
                {testimonyClues.length} 条
              </span>
            </div>
            <p className="investigation-category-desc">
              角色证词，可通过对话获取
            </p>
          </Card>

          <Card className="investigation-category">
            <div className="investigation-category-header">
              <Badge variant="document">文书</Badge>
              <span className="investigation-category-count">
                {documentClues.length} 条
              </span>
            </div>
            <p className="investigation-category-desc">
              文档证据，需要仔细阅读
            </p>
          </Card>
        </div>
      </div>

      {/* Clue Detail Modal */}
      <Modal
        isOpen={!!selectedClue}
        onClose={() => setSelectedClue(null)}
        title="线索详情"
        size="lg"
      >
        {selectedClue && (
          <div className="investigation-clue-detail">
            {(() => {
              const clue = allClues.find((c) => c.id === selectedClue);
              if (!clue) return null;
              return (
                <>
                  <div className="investigation-clue-detail-header">
                    <Badge
                      variant={
                        clue.type === 'physical'
                          ? 'physical'
                          : clue.type === 'testimony'
                          ? 'testimony'
                          : 'document'
                      }
                    >
                      {clue.type === 'physical' ? '物证' : clue.type === 'testimony' ? '证词' : '文书'}
                    </Badge>
                    <span className="investigation-clue-detail-holder">
                      持有者: {clue.holder_name}
                    </span>
                  </div>
                  <p className="investigation-clue-detail-content">
                    {clue.content}
                  </p>
                </>
              );
            })()}
          </div>
        )}
      </Modal>

      {/* Accuse Modal */}
      <Modal
        isOpen={showAccuseModal}
        onClose={() => {
          setShowAccuseModal(false);
          setSelectedSuspect(null);
        }}
        title="指认凶手"
        size="md"
      >
        <div className="accuse-modal">
          <div className="accuse-warning">
            <AlertTriangle size={20} />
            <p>
              你只有 <strong>1 次</strong> 指认机会！<br />
              指认正确则好人胜利，错误则凶手逃脱。
            </p>
          </div>

          <div className="accuse-suspects">
            <h4>选择你要指认的角色：</h4>
            <div className="accuse-suspect-grid">
              {allCharactersForDisplay.map((char) => (
                <Card
                  key={char.id}
                  variant={selectedSuspect === char.name ? 'gold-border' : 'default'}
                  className={`accuse-suspect-card ${
                    selectedSuspect === char.name ? 'selected' : ''
                  } ${char.id === state.player?.id ? 'is-player-character' : ''}`}
                  onClick={() => setSelectedSuspect(char.name)}
                  hoverable
                >
                  {char.id === state.player?.id && (
                    <Badge variant="default" className="accuse-player-badge">
                      当前角色
                    </Badge>
                  )}
                  <Avatar
                    name={char.name}
                    size="lg"
                    showBorder={selectedSuspect === char.name}
                  />
                  <div className="accuse-suspect-info">
                    <span className="accuse-suspect-name">{char.name}</span>
                    <span className="accuse-suspect-identity">{char.public_identity}</span>
                  </div>
                  {selectedSuspect === char.name && (
                    <div className="accuse-selected-badge">
                      <Check size={14} />
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </div>

          <div className="accuse-actions">
            <Button
              variant="ghost"
              onClick={() => {
                setShowAccuseModal(false);
                setSelectedSuspect(null);
              }}
            >
              取消
            </Button>
            <Button
              variant="danger"
              onClick={handleAccuse}
              disabled={!selectedSuspect}
              isLoading={isAccusing}
            >
              确认指认
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
