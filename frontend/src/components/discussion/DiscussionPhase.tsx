// Discussion Phase — 聊天布局由外壳决定高度，列表内部滚动
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { MessageSquare, Send, Vote, ArrowRight, Search, AlertTriangle, Check } from 'lucide-react';
import { useGame } from '../../context/useGame';
import { Button, Modal, AccuseModal, TypingIndicator, useToast, EvidenceNotebook } from '../common';
import { ChatMessage } from './ChatMessage';
import './DiscussionPhase.css';
import { isAndroid } from '../../api/native';
import { clueTitle, clueTypeLabel, visibleClues } from '../../utils/playerText';
import { emptyDiscussionDraft, loadDiscussionDraft, saveDiscussionDraft, type DiscussionDraft } from '../../utils/discussionDraft';

export function DiscussionPhase() {
  const {
    state,
    speak,
    startVoting,
    accuse,
    returnToInvestigation,
    startNextRound,
    refreshDiscussionHistory,
  } = useGame();
  const { notify } = useToast();
  const [draft, setDraft] = useState<DiscussionDraft>(() => emptyDiscussionDraft(state.characters.find(c => c.id !== state.player?.id)?.id));
  const draftRef = useRef(draft);
  const { message, targetId, evidenceId } = draft;
  const editedRef = useRef(false);
  const [selection, setSelection] = useState<'target' | 'evidence' | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [showAccuseModal, setShowAccuseModal] = useState(false);
  const [isAccusing, setIsAccusing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(true);
  const [following, setFollowing] = useState(true);
  const [readCount, setReadCount] = useState(state.currentDiscussionMessages.length);

  const isSpeaking = state.isSpeaking;
  const playerName = state.player?.name;
  const quickModeNeedsAnotherRound =
    state.mode === 'quick' && state.round < state.maxRounds;
  const allClues = visibleClues([...state.clues, ...state.scenePublicClues]);
  const targets = state.characters.filter(c => c.id !== state.player?.id);
  const selectedEvidence = allClues.find(c => c.id === evidenceId);
  const openSelection = (value: 'target' | 'evidence') => {
    (document.activeElement as HTMLElement | null)?.blur();
    setSelection(value);
  };

  // 角色名 → 角色信息（避免每条消息都 find 一遍）
  const characterByName = useMemo(
    () => new Map(state.characters.map((c) => [c.name, c])),
    [state.characters],
  );

  // 进入阶段时若本地无消息，拉取持久化的讨论记录
  useEffect(() => {
    if (state.currentDiscussionMessages.length === 0) {
      refreshDiscussionHistory();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (followRef.current) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.currentDiscussionMessages.length, isSpeaking]);

  useEffect(() => {
    if (!state.gameId) return;
    let cancelled = false;
    void loadDiscussionDraft(state.gameId, draftRef.current.targetId).then(value => {
      if (!cancelled && !editedRef.current) { draftRef.current = value; setDraft(value); }
    }).catch(() => notify('草稿读取失败', 'error'));
    return () => { cancelled = true; };
  }, [state.gameId, notify]);

  const editDraft = (patch: Partial<DiscussionDraft>) => {
    editedRef.current = true;
    const value = { ...draftRef.current, ...patch };
    draftRef.current = value;
    setDraft(value);
    if (state.gameId) {
      void saveDiscussionDraft(state.gameId, value).catch(() => notify('草稿保存失败', 'error'));
    }
  };
  const editMessage = (value: string) => editDraft({ message: value, pendingActionId: undefined });
  const setTargetId = (value: string) => editDraft({ targetId: value });
  const setEvidenceId = (value: string) => editDraft({ evidenceId: value });

  useEffect(() => {
    const actionId = draft.pendingActionId;
    if (!actionId || !state.gameId || !state.currentDiscussionMessages.some(m => m.action_id === actionId && m.kind === 'question')) return;
    const cleared = { ...draftRef.current, message: '', evidenceId: '', pendingActionId: undefined };
    draftRef.current = cleared;
    const timer = window.setTimeout(() => setDraft(cleared), 0);
    void saveDiscussionDraft(state.gameId, cleared).catch(() => notify('草稿保存失败', 'error'));
    return () => window.clearTimeout(timer);
  }, [draft.pendingActionId, state.currentDiscussionMessages, state.gameId, notify]);

  const handleSend = async () => {
    const text = message.trim();
    if (!text || isSpeaking) return;
    const actionId = crypto.randomUUID();
    editDraft({ pendingActionId: actionId });
    followRef.current = true;
    setFollowing(true);
    const result = await speak(text, { target_id: targetId || undefined, presented_clue_ids: evidenceId ? [evidenceId] : [], action_id: actionId });
    if (!result.recorded && draftRef.current.pendingActionId === actionId) editDraft({ pendingActionId: undefined });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // isComposing：中文输入法组词期间的回车不发送
    if (!isAndroid && e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTransitionToVoting = async () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    try {
      await startVoting();
    } catch (err) {
      notify(err instanceof Error ? err.message : '进入投票失败', 'error');
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleReturnToInvestigation = async () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    try {
      await returnToInvestigation();
    } catch (err) {
      notify(err instanceof Error ? err.message : '返回搜证失败', 'error');
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleNextRound = async () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    try { await startNextRound(); }
    catch (err) { notify(err instanceof Error ? err.message : '开启下一轮失败', 'error'); }
    finally { setIsTransitioning(false); }
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

  return (
    <div className="discussion-phase">
      <div className="discussion-topbar">
        <div className="discussion-topbar-title">
          <MessageSquare size={18} />
          <h2>讨论阶段</h2>
          <span className="discussion-round">
            回合 {state.round} / {state.maxRounds}
          </span>
          {state.mode === 'quick' && <small>{state.roundProgress?.investigated ? '调查完成' : '待调查'} · {state.roundProgress?.discussed ? '讨论完成' : '待发言'}</small>}
        </div>
        <div className="discussion-actions">
          {state.accusationPoints > 0 && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setShowAccuseModal(true)}
              disabled={isSpeaking || isTransitioning}
              className="discussion-action"
            >
              <AlertTriangle size={14} />
              提前结案
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReturnToInvestigation}
            isLoading={isTransitioning}
            disabled={isSpeaking}
            className="discussion-action"
          >
            <Search size={14} />
            补充调查
          </Button>
          {quickModeNeedsAnotherRound && <Button variant="primary" size="sm" onClick={handleNextRound}
            disabled={isSpeaking || isTransitioning || !state.availableActions.includes('next_round')} className="discussion-action">
            <ArrowRight size={14} />下一轮调查
          </Button>}
          {!quickModeNeedsAnotherRound &&
          <Button
            variant="primary"
            size="sm"
            onClick={handleTransitionToVoting}
            isLoading={isTransitioning}
            disabled={isSpeaking || (state.mode === 'quick' && !state.availableActions.includes('vote'))}
            className="discussion-action"
          >
            <Vote size={14} />
            {quickModeNeedsAnotherRound ? `还需 ${state.maxRounds - state.round} 轮` : state.mode === 'quick' && !state.availableActions.includes('vote') ? '先发表本轮推论' : '进入投票'}
            <ArrowRight size={14} />
          </Button>}
        </div>
      </div>

      <div className="discussion-messages" onScroll={e => {
        const list = e.currentTarget;
        const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 80;
        followRef.current = nearBottom;
        setFollowing(nearBottom);
        if (nearBottom) setReadCount(state.currentDiscussionMessages.length);
      }}>
        {state.currentDiscussionMessages.length === 0 ? (
          <div className="discussion-empty">
            <MessageSquare size={40} />
            <p>还没有发言</p>
            <span>开始讨论，发表你的看法</span>
          </div>
        ) : (
          state.currentDiscussionMessages.map((msg, index) => (
            <ChatMessage
              key={`${msg.speaker}-${index}`}
              message={msg}
              isPlayer={msg.speaker === playerName}
              character={characterByName.get(msg.speaker)}
              clues={allClues}
            />
          ))
        )}
        {isSpeaking && <TypingIndicator label="角色们正在思考回应" />}
        {!following && state.currentDiscussionMessages.length > readCount && <button type="button" className="discussion-new-messages"
          onClick={() => { followRef.current = true; setFollowing(true); messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }}>查看新消息 ↓</button>}
        <div ref={messagesEndRef} />
      </div>

      <div className="discussion-input-area">
        {isAndroid ? <>
          <div className="discussion-mobile-options">
            <button type="button" disabled={isSpeaking} onClick={() => openSelection('target')}>
              <span>询问 · {targets.find(c => c.id === targetId)?.name || `全员（${targets.length}人）`}</span><span>⌄</span>
            </button>
            <button type="button" disabled={isSpeaking} onClick={() => openSelection('evidence')}>
              <span>{selectedEvidence ? `出示 · ${clueTitle(selectedEvidence)}` : '选择证据'}</span><span>⌄</span>
            </button>
          </div>
          {!message && !isSpeaking && <div className="discussion-suggestions" aria-label="提问建议">
            <button type="button" onClick={() => editMessage(selectedEvidence ? '请解释这条证据与你的关系。' : '案发时你在哪里？')}>
              {selectedEvidence ? '询问这条证据' : '询问不在场证明'}
            </button>
            <button type="button" onClick={() => editMessage('你注意到哪些可疑的事情？')}>询问疑点</button>
          </div>}
        </> : <div className="discussion-question-options">
          <label>询问对象
            <select value={targetId} onChange={(e) => setTargetId(e.target.value)} disabled={isSpeaking}>
              <option value="">全员讨论（{targets.length}人回应）</option>
              {state.characters.filter((c) => c.id !== state.player?.id).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>出示证据
            <select value={evidenceId} onChange={(e) => setEvidenceId(e.target.value)} disabled={isSpeaking}>
              <option value="">不出示</option>
              {allClues.map((c) => <option key={c.id} value={c.id}>{clueTypeLabel(c.type)} · {clueTitle(c)}</option>)}
            </select>
          </label>
        </div>}
        <div className="discussion-input-wrapper">
          <textarea
            className="discussion-input"
            aria-label="讨论发言"
            value={message}
            onChange={(e) => editMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="写下你的台词…"
            rows={2}
            maxLength={500}
            disabled={isSpeaking}
          />
          <Button
            variant="primary"
            onClick={handleSend}
            isLoading={isSpeaking}
            disabled={!message.trim() || state.connectionLost}
            className="discussion-send-btn"
            aria-label="发送"
          >
            <Send size={16} />
          </Button>
        </div>
        <p className="discussion-hint">Enter 发送 · Shift+Enter 换行</p>
      </div>

      <Modal isOpen={selection !== null} onClose={() => setSelection(null)}
        title={selection === 'target' ? '选择询问对象' : '选择出示的证据'}>
        <div className="discussion-selection-list">
          <button type="button" aria-pressed={selection === 'target' ? !targetId : !evidenceId}
            onClick={() => { if (selection === 'target') setTargetId(''); else setEvidenceId(''); setSelection(null); }}>
            <strong className="discussion-choice-title">{selection === 'target' ? `全员讨论（${targets.length}人回应）` : '不出示证据'}
              {(selection === 'target' ? !targetId : !evidenceId) && <span className="discussion-choice-selected"><Check size={14} />已选择</span>}
            </strong>
          </button>
          {selection === 'target' ? targets.map(c => <button type="button" key={c.id} aria-pressed={targetId === c.id}
            onClick={() => { setTargetId(c.id); setSelection(null); }}>
            <strong className="discussion-choice-title">{c.name}
              {targetId === c.id && <span className="discussion-choice-selected"><Check size={14} />已选择</span>}
            </strong><small>{c.public_identity}</small>
          </button>) : <EvidenceNotebook selectedId={evidenceId} onSelect={id => { setEvidenceId(id); setSelection(null); }} />}
          {selection === 'evidence' && allClues.length === 0 && <p>先返回搜证，调查一条线索。</p>}
        </div>
      </Modal>

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
