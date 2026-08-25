// Voting Phase — 投票、等待计票、结果展示
import { useEffect, useState } from 'react';
import { Vote, AlertTriangle, Check, ArrowLeft } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Avatar, Modal, useToast } from '../common';
import type { VoteResponse } from '../../api/types';
import './VotingPhase.css';

export function VotingPhase() {
  const { state, vote, refreshStatus, returnToInvestigation, nextPhase } =
    useGame();
  const { notify } = useToast();
  const [selectedCharacter, setSelectedCharacter] = useState<string | null>(null);
  const [isVoting, setIsVoting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [voteResult, setVoteResult] = useState<VoteResponse | null>(null);

  // 等待计票的计时提示
  useEffect(() => {
    if (!isVoting) return;
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(timer);
  }, [isVoting]);

  const handleVote = async () => {
    if (!selectedCharacter || isVoting) return;
    setIsVoting(true);
    setShowConfirmModal(false);
    try {
      const result = await vote(selectedCharacter);
      setVoteResult(result);
      // 游戏结束时 context 已把阶段切到 reveal，本组件会随之卸载
      if (!result.game_ended) {
        await refreshStatus();
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : '投票失败', 'error');
    } finally {
      setIsVoting(false);
    }
  };

  // 平票/票数不足：回到搜证再进入讨论
  const handleReturnToDiscussion = async () => {
    try {
      await returnToInvestigation();
      await nextPhase();
    } catch (err) {
      notify(err instanceof Error ? err.message : '返回讨论失败', 'error');
    }
  };

  return (
    <div className="voting-phase">
      <div className="voting-header">
        <div className="voting-icon">
          <Vote size={24} />
        </div>
        <h2 className="voting-title">表决</h2>
        <p className="voting-subtitle">圈定你认为是凶手的角色，落笔为凭</p>
      </div>

      <Card className="voting-instructions">
        <div className="voting-instructions-content">
          <AlertTriangle size={18} className="voting-warning-icon" />
          <div>
            <h4>投票规则</h4>
            <p>
              所有存活角色各投一票，达到法定票数（存活人数的 2/3 + 1）
              即可淘汰得票最高者。淘汰凶手则好人胜利；投错则凶手逃脱。
              平局或票数不足时回到讨论阶段继续推理。
            </p>
          </div>
        </div>
      </Card>

      {/* 计票等待态 */}
      {isVoting && (
        <Card className="voting-waiting">
          <div className="voting-waiting-spinner" aria-hidden="true" />
          <p className="voting-waiting-title">唱票中…</p>
          <p className="voting-waiting-hint">
            各位角色正在权衡与抉择（已等待 {elapsed} 秒）
          </p>
        </Card>
      )}

      {/* 角色选择区域：投票后隐藏 */}
      {!voteResult && !isVoting && (
        <>
          <div className="voting-characters">
            <h3 className="voting-section-title">选择凶手</h3>
            <div className="voting-character-grid">
              {state.characters
                .filter((c) => c.id !== state.player?.id)
                .map((char) => (
                  <Card
                    key={char.id}
                    variant={
                      selectedCharacter === char.name ? 'gold-border' : 'default'
                    }
                    className={`voting-character-card ${
                      selectedCharacter === char.name ? 'selected' : ''
                    }`}
                    onClick={() => setSelectedCharacter(char.name)}
                    hoverable
                  >
                    <Avatar
                      name={char.name}
                      size="lg"
                      showBorder={selectedCharacter === char.name}
                    />
                    <div className="voting-character-info">
                      <span className="voting-character-name">{char.name}</span>
                      <span className="voting-character-identity">
                        {char.public_identity}
                      </span>
                    </div>
                    {selectedCharacter === char.name && (
                      <div className="voting-selected-badge">
                        <Check size={14} />
                      </div>
                    )}
                  </Card>
                ))}
            </div>
          </div>

          <div className="voting-actions">
            <Button
              variant="primary"
              size="lg"
              onClick={() => setShowConfirmModal(true)}
              disabled={!selectedCharacter}
            >
              <Vote size={16} />
              落笔表决
            </Button>
          </div>
        </>
      )}

      {/* 投票未结束（平局/票数不足）的结果展示 */}
      {voteResult && !voteResult.game_ended && (
        <Card className="voting-result-card result-tie">
          <h3>投票未达成结果</h3>
          <p className="voting-result-message">{voteResult.result}</p>

          {Object.keys(voteResult.votes).length > 0 && (
            <div className="voting-result-detail">
              <h4>投票明细</h4>
              {Object.entries(voteResult.votes).map(([voter, target]) => (
                <div key={voter} className="voting-result-detail-row">
                  <span className="voting-result-voter">{voter}</span>
                  <span className="voting-result-arrow">→</span>
                  <span className="voting-result-target">{target}</span>
                </div>
              ))}
            </div>
          )}

          <div className="voting-tie-actions">
            <p className="voting-tie-hint">需要继续讨论后再投票</p>
            <Button variant="secondary" onClick={handleReturnToDiscussion}>
              <ArrowLeft size={15} />
              返回讨论阶段
            </Button>
          </div>
        </Card>
      )}

      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title="签署表决"
        size="sm"
      >
        <div className="voting-confirm-content">
          <p>
            你确定要投票给 <strong>{selectedCharacter}</strong> 吗？
          </p>
          <p className="voting-confirm-hint">
            等待其他角色投票期间可以重新投票改主意
          </p>
          <div className="voting-confirm-actions">
            <Button variant="ghost" onClick={() => setShowConfirmModal(false)}>
              取消
            </Button>
            <Button variant="danger" onClick={handleVote}>
              落笔表决
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
