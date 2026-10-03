import type { Clue } from '../api/types';

export const clueTypeLabel = (type: string) =>
  ({ physical: '物证', testimony: '证词', document: '文书' }[type] || '线索');

export function clueTitle(clue: Pick<Clue, 'content' | 'type' | 'title'>): string {
  if (clue.title?.trim()) return clue.title.trim();
  const text = clue.content.trim().replace(/^【([^】]+)】/, '$1：');
  const heading = text.split(/[：:。；\n]/, 1)[0];
  return heading ? heading.slice(0, 18) + (heading.length > 18 ? '…' : '') : clueTypeLabel(clue.type);
}

export function visibleClues(clues: Clue[]): Clue[] {
  return [...new Map(clues.map(clue => [clue.id, clue])).values()];
}

/** Present canonical player metadata separately, without rewriting saved speech. */
export function presentPlayerMessage(message: string, clues: Clue[]) {
  let text = message;
  let target = '';
  const evidence: string[] = [];
  const targetMatch = text.match(/^【询问([^】\n]+)】/);
  if (targetMatch) { target = targetMatch[1]; text = text.slice(targetMatch[0].length); }
  const footer = text.match(/\n【出示证据】((?:clue_[A-Za-z0-9_-]+)(?:、clue_[A-Za-z0-9_-]+)*)$/);
  if (footer) {
    const byId = new Map(clues.map(clue => [clue.id, clue]));
    for (const id of footer[1].split('、')) {
      const clue = byId.get(id);
      evidence.push(clue ? clueTitle(clue) : '已出示的证据');
    }
    text = text.slice(0, -footer[0].length);
  }
  return { text, target, evidence };
}
