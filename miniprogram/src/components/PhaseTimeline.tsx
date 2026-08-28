import { Text, View } from '@tarojs/components'
import type { GamePhase } from '@/types/game'
import './PhaseTimeline.scss'

const PHASES: Array<{ key: GamePhase; label: string; short: string }> = [
  { key: 'introduction', label: '介绍', short: 'INTRO' },
  { key: 'investigation', label: '调查', short: 'SEARCH' },
  { key: 'discussion', label: '讨论', short: 'DEBATE' },
  { key: 'voting', label: '表决', short: 'VOTE' },
  { key: 'reveal', label: '结案', short: 'REVEAL' },
]

export function PhaseTimeline({ phase }: { phase: GamePhase }) {
  const activeIndex = PHASES.findIndex((item) => item.key === phase)

  return (
    <View className='phase-timeline'>
      {PHASES.map((item, index) => (
        <View
          key={item.key}
          className={`phase-step ${index === activeIndex ? 'phase-step--active' : ''} ${
            index < activeIndex ? 'phase-step--done' : ''
          }`}
        >
          <View className='phase-step__track'>
            <View className='phase-step__dot'>{String(index + 1).padStart(2, '0')}</View>
          </View>
          <Text className='phase-step__label'>{item.label}</Text>
          <Text className='phase-step__short'>{item.short}</Text>
        </View>
      ))}
    </View>
  )
}
