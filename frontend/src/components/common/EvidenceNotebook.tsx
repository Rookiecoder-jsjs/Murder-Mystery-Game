import { useGame } from '../../context/useGame';
import { Check } from 'lucide-react';
import { clueTitle, clueTypeLabel, visibleClues } from '../../utils/playerText';
import './EvidenceNotebook.css';

/** Read-only authorized evidence; opening it never changes phase or ownership. */
export function EvidenceNotebook({ onSelect, selectedId }: { onSelect?: (id: string) => void; selectedId?: string }) {
  const { state } = useGame();
  const clues = visibleClues([...state.clues, ...state.scenePublicClues]);
  return <div className="evidence-notebook">
    {clues.length === 0 && <p>暂无已掌握的证据，先选择调查方向。</p>}
    {clues.map(clue => <details className="evidence-note" key={clue.id} data-selected={clue.id === selectedId || undefined}>
      <summary>
        <span className="evidence-note-heading"><strong>{clueTitle(clue)}</strong>
          {clue.id === selectedId && <span className="evidence-note-selected"><Check size={14} />已选择</span>}
        </span>
        <span className="evidence-note-meta">{clueTypeLabel(clue.type)} · {clue.is_revealed ? '已公开' : '你已掌握'} · 展开原文</span>
      </summary>
      <p>{clue.content}</p>
      {onSelect && <button type="button" className="btn btn-secondary" aria-pressed={clue.id === selectedId}
        onClick={() => onSelect(clue.id)}>{clue.id === selectedId ? '已选择这条证据' : '选择这条证据'}</button>}
    </details>)}
  </div>;
}
