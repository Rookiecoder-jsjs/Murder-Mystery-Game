import { Link2, ShieldAlert, Split } from 'lucide-react';
import type { Clue } from '../../api/types';
import './EvidenceChain.css';

interface EvidenceChainProps {
  clues: Clue[];
}

const relationLabels: Record<string, string> = {
  supports: '支持',
  contradiction: '矛盾',
  timeline: '时间线',
};

function shortContent(clue: Clue): string {
  return clue.content.length > 32 ? `${clue.content.slice(0, 32)}…` : clue.content;
}

export function EvidenceChain({ clues }: EvidenceChainProps) {
  const byId = new Map(clues.map((clue) => [clue.id, clue]));
  const links = clues.flatMap((clue) =>
    (clue.relations ?? [])
      .filter((relation) => byId.has(relation.target_id))
      .map((relation) => ({ source: clue, target: byId.get(relation.target_id)!, relation })),
  );

  return (
    <section className="evidence-chain" aria-label="证据链">
      <div className="evidence-chain-header">
        <div>
          <span className="evidence-chain-kicker">CASE BOARD / LINKS</span>
          <h3><Link2 size={17} /> 证据链</h3>
        </div>
        <span>{links.length} 条关联</span>
      </div>

      {links.length === 0 ? (
        <div className="evidence-chain-empty">
          <Split size={17} />
          <span>目前还是独立线索。继续调查，寻找能互相印证或冲突的证据。</span>
        </div>
      ) : (
        <div className="evidence-chain-links">
          {links.map(({ source, target, relation }, index) => (
            <div className="evidence-chain-link" key={`${source.id}-${target.id}-${index}`}>
              <div className="evidence-chain-node">
                <span className="evidence-chain-node-id">{source.id}</span>
                <strong>{shortContent(source)}</strong>
              </div>
              <div className={`evidence-chain-relation evidence-chain-relation--${relation.type}`}>
                {relation.type === 'contradiction' ? <ShieldAlert size={14} /> : <Link2 size={14} />}
                <span>{relation.label || relationLabels[relation.type] || '关联'}</span>
              </div>
              <div className="evidence-chain-node evidence-chain-node--target">
                <span className="evidence-chain-node-id">{target.id}</span>
                <strong>{shortContent(target)}</strong>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
