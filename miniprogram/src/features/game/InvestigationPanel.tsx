import Taro from '@tarojs/taro'
import { Button, Text, View } from '@tarojs/components'
import { useMemo, useState } from 'react'
import { ClueCard, SuspectPicker } from '@/components'
import { useGame } from '@/store/game-context'
import type { Clue } from '@/types/game'
import { showError, showNotice } from '@/utils/feedback'
import './InvestigationPanel.scss'

export function InvestigationPanel() {
  const { state, investigate, nextPhase, accuse } = useGame()
  const [latestClue, setLatestClue] = useState<Clue | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [selectedId, setSelectedId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [transitioning, setTransitioning] = useState(false)

  const suspects = useMemo(
    () => state.characters.filter((item) => item.id !== state.player?.id),
    [state.characters, state.player?.id],
  )

  const search = async (leadId?: string) => {
    try {
      const found = await investigate(leadId)
      if (found[0]) {
        setLatestClue(found[0])
        showNotice('发现一条新线索')
      }
    } catch (error) {
      showError(error)
    }
  }

  const enterDiscussion = async () => {
    if (transitioning) return
    setTransitioning(true)
    try {
      await nextPhase()
    } catch (error) {
      showError(error)
    } finally {
      setTransitioning(false)
    }
  }

  const confirmAccusation = async () => {
    const character = suspects.find((item) => item.id === selectedId)
    if (!character) return
    const confirm = await Taro.showModal({
      title: `指控 ${character.name}？`,
      content: '指控机会十分有限。一旦落印，本次判断不可撤销。',
      confirmText: '确认指控',
      confirmColor: '#9d3328',
    })
    if (!confirm.confirm) return

    setSubmitting(true)
    try {
      const result = await accuse(character.name)
      setPickerOpen(false)
      if (result.game_ended && state.gameId) {
        Taro.redirectTo({ url: `/pages/reveal/index?gameId=${state.gameId}` })
      } else {
        showNotice(result.message)
      }
    } catch (error) {
      showError(error)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className='game-panel investigation-panel'>
      <View className='game-panel__heading'>
        <Text className='section-kicker'>ACT II · INVESTIGATION</Text>
        <Text className='section-title'>案发现场</Text>
        <Text className='section-desc'>先记录公开事实，再主动搜查新的证物。每条线索都可能被另一条线索重新解释。</Text>
      </View>

      <View className='investigation-panel__scene'>
        <View className='investigation-panel__scene-no'>SCENE / 01</View>
        <View className='investigation-panel__scene-light' />
        <Text className='investigation-panel__scene-title'>封锁区域 · 首轮勘察</Text>
        <Text className='investigation-panel__scene-copy'>现场仍保留着案发当夜的痕迹。不要只寻找“像答案”的东西，也要留意那些不合时宜的小细节。</Text>
        <View className='investigation-panel__scene-meta'>
          <View><Text>{state.scenePublicClues.length}</Text><Text>公开线索</Text></View>
          <View><Text>{state.clues.length}</Text><Text>私有证物</Text></View>
          <View><Text>{state.accusationPoints}</Text><Text>指控机会</Text></View>
        </View>
      </View>

      {latestClue && (
        <View className='investigation-panel__latest'>
          <Text className='field-label'>刚刚发现</Text>
          <ClueCard clue={latestClue} featured />
        </View>
      )}

      {state.mode === 'quick' ? (
        <View className='investigation-panel__leads paper-card'>
          <View className='investigation-panel__section-head'>
            <View>
              <Text className='field-label'>QUICK CASE · ROUND {state.round}</Text>
              <Text className='investigation-panel__leads-title'>选择调查方向</Text>
            </View>
            <Text>{state.investigationOptions.length} 个突破口</Text>
          </View>
          <View className='investigation-panel__lead-list'>
            {state.investigationOptions.map((option) => (
              <Button
                key={option.id}
                className='investigation-panel__lead'
                disabled={state.isLoading}
                onClick={() => search(option.id)}
              >
                <Text className='investigation-panel__lead-kind'>{option.kind.toUpperCase()}</Text>
                <Text className='investigation-panel__lead-title'>{option.title}</Text>
                <Text className='investigation-panel__lead-copy'>{option.description}</Text>
                <Text className='investigation-panel__lead-cta'>调查此方向 →</Text>
              </Button>
            ))}
          </View>
        </View>
      ) : (
        <View className='investigation-panel__actions paper-card'>
          <View>
            <Text>主动搜查</Text>
            <Text>从尚未发现的证物中调取一条线索</Text>
          </View>
          <Button className='primary-button' onClick={() => search()}>⌕ 搜查现场</Button>
        </View>
      )}

      {state.lastEvent && (
        <View className='investigation-panel__event paper-card'>
          <Text className='investigation-panel__event-mark'>!</Text>
          <View>
            <Text className='investigation-panel__event-title'>{state.lastEvent.title}</Text>
            <Text>{state.lastEvent.message}</Text>
          </View>
        </View>
      )}

      <View className='investigation-panel__section'>
        <View className='investigation-panel__section-head'>
          <Text className='field-label'>公开现场记录</Text>
          <Text>{state.scenePublicClues.length} ITEMS</Text>
        </View>
        <View className='investigation-panel__clues'>
          {state.scenePublicClues.length ? state.scenePublicClues.map((clue) => (
            <ClueCard key={clue.id} clue={clue} />
          )) : (
            <View className='paper-card empty-state'>现场暂无公开线索</View>
          )}
        </View>
      </View>

      <View className='investigation-panel__section'>
        <View className='investigation-panel__section-head'>
          <Text className='field-label'>你的证据袋</Text>
          <Text>{state.clues.length} ITEMS</Text>
        </View>
        <View className='investigation-panel__clues'>
          {state.clues.length ? state.clues.map((clue) => (
            <ClueCard key={clue.id} clue={clue} />
          )) : (
            <View className='paper-card empty-state'>证据袋还是空的，先搜查现场</View>
          )}
        </View>
      </View>

      <View className='investigation-panel__footer'>
        <Button
          className='secondary-button'
          disabled={state.accusationPoints < 1}
          onClick={() => setPickerOpen(true)}
        >
          直接指控
        </Button>
        <Button
          className='primary-button'
          disabled={transitioning}
          onClick={enterDiscussion}
        >
          带着线索进入讨论
        </Button>
      </View>

      <SuspectPicker
        visible={pickerOpen}
        title='锁定你认为的凶手'
        note={`你还剩 ${state.accusationPoints} 次直接指控机会`}
        characters={suspects}
        selectedId={selectedId}
        confirmText='落下指控印'
        dangerous
        loading={submitting}
        onSelect={setSelectedId}
        onClose={() => setPickerOpen(false)}
        onConfirm={confirmAccusation}
      />
    </View>
  )
}
