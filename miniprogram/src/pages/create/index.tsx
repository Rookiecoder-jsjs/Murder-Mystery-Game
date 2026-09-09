import Taro from '@tarojs/taro'
import { Button, Text, Textarea, View } from '@tarojs/components'
import { useEffect, useState } from 'react'
import { CaseHeader } from '@/components'
import { useGame } from '@/store/game-context'
import type { GameMode } from '@/types/game'
import { showError } from '@/utils/feedback'
import './index.scss'

const TOPICS = [
  '豪华邮轮谋杀案',
  '古堡深夜的神秘死亡',
  '上海租界戏院迷案',
  '密室中的摄影师之死',
]

const GENERATION_STEPS = [
  '勾勒时代与案发现场',
  '建立人物关系与秘密',
  '推演诡计和证据闭环',
  '绘制角色人物肖像',
  '密封完整案件卷宗',
]

export default function CreatePage() {
  const { createGame } = useGame()
  const [topic, setTopic] = useState('')
  const [mode, setMode] = useState<GameMode>('quick')
  const [creating, setCreating] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!creating) return undefined
    const timer = setInterval(() => setElapsed((value) => value + 1), 1000)
    return () => clearInterval(timer)
  }, [creating])

  const handleCreate = async () => {
    const trimmed = topic.trim()
    if (!trimmed || creating) return
    setCreating(true)
    setElapsed(0)
    try {
      const gameId = await createGame(trimmed, mode)
      Taro.redirectTo({ url: `/pages/game/index?gameId=${gameId}` })
    } catch (error) {
      showError(error)
      setCreating(false)
    }
  }

  if (creating) {
    const activeStep = Math.min(4, Math.floor(elapsed / 24))
    return (
      <View className='page-shell create-page'>
        <CaseHeader title='卷宗生成中' eyebrow='ARCHIVE IN PROGRESS' showBack />
        <View className='create-progress'>
          <View className='create-progress__lamp' />
          <Text className='create-progress__serial'>CASE / GENERATING / T+{String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}</Text>
          <Text className='create-progress__title'>角色正在逐一入场</Text>
          <Text className='create-progress__topic'>《{topic}》</Text>

          <View className='create-progress__portraits'>
            {[0, 1, 2, 3].map((item) => (
              <View
                key={item}
                className={`create-progress__portrait ${elapsed > item * 8 ? 'create-progress__portrait--ready' : ''}`}
                style={{ animationDelay: `${item * 0.12}s` }}
              >
                <View className='create-progress__silhouette'>?</View>
                <Text>人物档案 {String(item + 1).padStart(2, '0')}</Text>
              </View>
            ))}
          </View>

          <View className='create-progress__ledger'>
            {GENERATION_STEPS.map((step, index) => (
              <View key={step} className={`create-progress__step ${index < activeStep ? 'is-done' : ''} ${index === activeStep ? 'is-active' : ''}`}>
                <Text>{String(index + 1).padStart(2, '0')}</Text>
                <Text>{step}</Text>
                <Text>{index < activeStep ? '已归档' : index === activeStep ? '誊录中' : '等待'}</Text>
              </View>
            ))}
          </View>

          <Text className='create-progress__notice'>生成故事与肖像通常需要 1–3 分钟，请保持本页开启</Text>
        </View>
      </View>
    )
  }

  return (
    <View className='page-shell create-page'>
      <CaseHeader title='新案登记' eyebrow='NEW CASE' showBack />
      <View className='paper-stage create-page__stage'>
        <View className='create-page__heading'>
          <Text className='section-kicker'>CASE APPLICATION</Text>
          <Text className='section-title'>给故事一个起点</Text>
          <Text className='section-desc'>你只需提供一个主题。人物关系、诡计、线索与肖像将由 AI 完整构筑。</Text>
        </View>

        <View className='create-form paper-card'>
          <Text className='create-form__index'>FORM · 01</Text>
          <Text className='field-label'>案件主题</Text>
          <Textarea
            className='archive-textarea create-form__textarea'
            value={topic}
            maxlength={100}
            placeholder='例如：1930年代上海，一艘即将离港的邮轮上发生离奇命案……'
            placeholderClass='archive-placeholder'
            onInput={(event) => setTopic(event.detail.value)}
          />
          <View className='create-form__counter'>{topic.length} / 100</View>

          <Text className='field-label create-form__mode-label'>调查节奏</Text>
          <View className='create-form__modes'>
            <Button className={mode === 'quick' ? 'is-selected' : ''} onClick={() => setMode('quick')}>
              <Text>速推模式</Text>
              <Text>三轮推进 · 10–15 分钟</Text>
            </Button>
            <Button className={mode === 'classic' ? 'is-selected' : ''} onClick={() => setMode('classic')}>
              <Text>经典模式</Text>
              <Text>自由调查 · 完整流程</Text>
            </Button>
          </View>

          <Text className='field-label create-form__suggestion-label'>灵感签</Text>
          <View className='create-form__suggestions'>
            {TOPICS.map((item) => (
              <Button
                key={item}
                className={topic === item ? 'is-selected' : ''}
                onClick={() => setTopic(item)}
              >
                {item}
              </Button>
            ))}
          </View>
        </View>

        <View className='create-page__promise'>
          <View><Text>01</Text><Text>完整案件</Text><Text>多重反转与证据闭环</Text></View>
          <View><Text>02</Text><Text>鲜活角色</Text><Text>每个人都有隐秘动机</Text></View>
          <View><Text>03</Text><Text>专属肖像</Text><Text>依据人物描述逐一生成</Text></View>
        </View>

        <Button className='primary-button create-page__submit' disabled={!topic.trim()} onClick={handleCreate}>
          提交登记 · 开始生成
        </Button>
        <Text className='create-page__random-note'>你将随机获得其中一位角色的秘密档案</Text>
      </View>
    </View>
  )
}
