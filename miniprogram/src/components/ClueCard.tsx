import { Text, View } from '@tarojs/components'
import type { Clue } from '@/types/game'
import './ClueCard.scss'

const CLUE_META = {
  physical: { label: '物证', glyph: '⌕' },
  testimony: { label: '证言', glyph: '“' },
  document: { label: '文书', glyph: '≡' },
}

export function ClueCard({ clue, featured = false }: { clue: Clue; featured?: boolean }) {
  const meta = CLUE_META[clue.type] || CLUE_META.physical

  return (
    <View className={`clue-card clue-card--${clue.type} ${featured ? 'clue-card--featured' : ''}`}>
      <View className='clue-card__pin' />
      <View className='clue-card__head'>
        <Text className='clue-card__glyph'>{meta.glyph}</Text>
        <Text className='clue-card__type'>{meta.label}</Text>
        <Text className='clue-card__id'>{clue.id.toUpperCase()}</Text>
      </View>
      <Text className='clue-card__content'>{clue.content}</Text>
      <View className='clue-card__foot'>
        <Text>来源 · {clue.holder_name}</Text>
        {clue.is_revealed && <Text className='clue-card__public'>公开</Text>}
      </View>
    </View>
  )
}
