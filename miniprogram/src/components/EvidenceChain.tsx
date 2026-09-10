import { Text, View } from '@tarojs/components'
import type { Clue } from '@/types/game'
import './EvidenceChain.scss'

const relationLabels: Record<string, string> = {
  supports: '支持',
  contradiction: '矛盾',
  timeline: '时间线',
}

function shortContent(clue: Clue) {
  return clue.content.length > 28 ? `${clue.content.slice(0, 28)}…` : clue.content
}

export function EvidenceChain({ clues }: { clues: Clue[] }) {
  const byId = new Map(clues.map((clue) => [clue.id, clue]))
  const links = clues.flatMap((clue) => (clue.relations || [])
    .filter((relation) => byId.has(relation.target_id))
    .map((relation) => ({ clue, target: byId.get(relation.target_id)!, relation })))

  return (
    <View className='evidence-chain paper-card'>
      <View className='evidence-chain__head'>
        <View>
          <Text className='field-label'>CASE BOARD / LINKS</Text>
          <Text className='evidence-chain__title'>证据链</Text>
        </View>
        <Text>{links.length} 条关联</Text>
      </View>
      {links.length === 0 ? (
        <View className='evidence-chain__empty'>
          <Text>目前还是独立线索。继续调查，寻找能互相印证或冲突的证据。</Text>
        </View>
      ) : (
        <View className='evidence-chain__links'>
          {links.map(({ clue, target, relation }, index) => (
            <View className='evidence-chain__link' key={`${clue.id}-${target.id}-${index}`}>
              <View className='evidence-chain__node'>
                <Text className='evidence-chain__id'>{clue.id}</Text>
                <Text>{shortContent(clue)}</Text>
              </View>
              <Text className={`evidence-chain__relation evidence-chain__relation--${relation.type}`}>
                {relationLabels[relation.type] || relation.label || '关联'}
              </Text>
              <View className='evidence-chain__node evidence-chain__node--target'>
                <Text className='evidence-chain__id'>{target.id}</Text>
                <Text>{shortContent(target)}</Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  )
}
