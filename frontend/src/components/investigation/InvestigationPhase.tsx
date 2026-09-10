// Investigation Phase — 搜证、线索板、指认凶手
import { useState } from 'react';
import { Search, Eye, MessageSquare, AlertTriangle, Zap } from 'lucide-react';
import { useGame } from '../../context/useGame';
import { Button, Card, Badge, Modal, AccuseModal, useToast } from '../common';
import { ClueCard } from './ClueCard';
import './InvestigationPhase.css';

export function InvestigationPhase() {
  const { state, nextPhase, accuse, investigate } = useGame();
  const { notify } = useToast();
  const [selectedClue, setSelectedClue] = useState<string | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [foundClueIds, setFoundClueIds] = useState<string[]>([]);
  const [showAccuseModal, setShowAccuseModal] = useState(false);
  const [isAccusing, setIsAccusing] = useState(false);
  const quickInvestigationComplete =
    state.mode === 'quick' && state.investigationActionsRemaining === 0;
  const canEnterDiscussion =
    state.mode !== 'quick' || state.investigationActionsRemaining === 0;

  const handleInvestigate = async (leadId?: string) => {
    if (isInvestigating) return;
    setIsInvestigating(true);
    try {
      const found = await investigate(leadId);
      // 新线索只在网格中出现一次（带「新发现」徽标），不再另渲染一份卡片
      setFoundClueIds(found.map((c) => c.id));
      if (found.length > 0) {
        notify(`发现了 ${found.length} 条新线索`, 'success');
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : '搜证失败', 'error');
    } finally {
      setIsInvestigating(false);
    }
  };

  const handleTransitionToDiscussion = async () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    try {
      await nextPhase();
    } catch (err) {
      notify(err instanceof Error ? err.message : '进入讨论失败', 'error');
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleAccuse = async (characterName: string) => {
    if (isAccusing) return;
    setIsAccusing(true);
    try {
      const result = await accuse(characterName);
      setShowAccuseModal(false);
      notify(result.message, result.correct ? 'success' : 'error');
    } catch (err) {
      notify(err instanceof Error ? err.message : '指认失败', 'error');
    } finally {
      setIsAccusing(false);
    }
  };

  const allClues = [...state.clues, ...state.scenePublicClues];
  const selectedClueObj = allClues.find((c) => c.id === selectedClue);

  return (
    <div className="investigation-phase">
      <div className="investigation-header">
        <div className="investigation-icon">
          <Search size={24} />
        </div>
        <h2 className="investigation-title">搜证阶段</h2>
        <p className="investigation-subtitle">调查线索，发现真相</p>
      </div>

      <div className="investigation-actions">
        <Button
          variant="primary"
          onClick={() => handleInvestigate()}
          isLoading={isInvestigating}
          className="investigation-action"
          disabled={state.mode === 'quick'}
        >
          <Search size={16} />
          {state.mode === 'quick' ? '请选择调查方向' : '搜证'}
        </Button>
        <Button
          variant="secondary"
          onClick={handleTransitionToDiscussion}
          isLoading={isTransitioning}
          disabled={!canEnterDiscussion}
          className="investigation-action"
        >
          <MessageSquare size={16} />
          进入讨论
        </Button>
        {state.accusationPoints > 0 && (
          <Button
            variant="danger"
            onClick={() => setShowAccuseModal(true)}
            className="investigation-action"
          >
            <AlertTriangle size={16} />
            指认凶手（剩余 {state.accusationPoints} 次）
          </Button>
        )}
      </div>

      {state.mode === 'quick' && (
        <div className="investigation-leads">
          <div className="investigation-leads-header">
            <div>
              <span className="investigation-leads-kicker">QUICK CASE / ROUND {state.round}</span>
              <h3><Zap size={16} /> 选择你的调查方向</h3>
            </div>
            <span className="investigation-leads-count">
              {quickInvestigationComplete
                ? '本轮调查已完成'
                : `剩余 ${state.investigationActionsRemaining ?? '不限'} 次调查`}
            </span>
          </div>
          <div className="investigation-leads-grid">
            {state.investigationOptions.map((option) => (
              <button
                type="button"
                key={option.id}
                className="investigation-lead-card"
                onClick={() => handleInvestigate(option.id)}
                disabled={isInvestigating || quickInvestigationComplete}
              >
                <span className="investigation-lead-card-index">LEAD / {option.kind.toUpperCase()}</span>
                <strong>{option.title}</strong>
                <span>{option.description}</span>
                <em>{isInvestigating ? '正在调取…' : '调查此方向 →'}</em>
              </button>
            ))}
          </div>
        </div>
      )}

      {state.lastEvent && (
        <div className="investigation-event" role="status">
          <span className="investigation-event-mark">!</span>
          <div>
            <strong>{state.lastEvent.title}</strong>
            <p>{state.lastEvent.message}</p>
          </div>
        </div>
      )}

      <div className="investigation-content">
        <Card className="investigation-clues-card">
          <div className="investigation-clues-header">
            <h3>
              <Eye size={16} />
              你的线索
            </h3>
            <Badge variant="gold">{state.clues.length} 条</Badge>
          </div>

          {state.clues.length === 0 ? (
            <div className="investigation-empty">
              <Search size={40} />
              <p>暂无线索</p>
              <span>点击「搜证」按钮获取新线索</span>
            </div>
          ) : (
            <div className="investigation-clues-grid">
              {state.clues.map((clue) => (
                <ClueCard
                  key={clue.id}
                  clue={clue}
                  isNew={foundClueIds.includes(clue.id)}
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
                <Eye size={16} />
                公开线索
              </h3>
              <Badge variant="info">{state.scenePublicClues.length} 条</Badge>
            </div>
            <div className="investigation-clues-grid">
              {state.scenePublicClues.map((clue) => (
                <ClueCard
                  key={clue.id}
                  clue={clue}
                  isNew={foundClueIds.includes(clue.id)}
                  onClick={() => setSelectedClue(clue.id)}
                />
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* 线索详情 */}
      <Modal
        isOpen={!!selectedClueObj}
        onClose={() => setSelectedClue(null)}
        title="线索详情"
        size="md"
      >
        {selectedClueObj && (
          <div className="investigation-clue-detail">
            <div className="investigation-clue-detail-header">
              <Badge
                variant={
                  selectedClueObj.type === 'physical'
                    ? 'physical'
                    : selectedClueObj.type === 'testimony'
                    ? 'testimony'
                    : 'document'
                }
              >
                {selectedClueObj.type === 'physical'
                  ? '物证'
                  : selectedClueObj.type === 'testimony'
                  ? '证词'
                  : '文书'}
              </Badge>
              <span className="investigation-clue-detail-holder">
                持有者：{selectedClueObj.holder_name}
              </span>
            </div>
            <p className="investigation-clue-detail-content">
              {selectedClueObj.content}
            </p>
          </div>
        )}
      </Modal>

      {/* 指认凶手 */}
      <AccuseModal
        isOpen={showAccuseModal}
        onClose={() => setShowAccuseModal(false)}
        characters={state.characters}
        playerId={state.player?.id}
        accusationPoints={state.accusationPoints}
        isAccusing={isAccusing}
        onConfirm={handleAccuse}
      />
    </div>
  );
}
