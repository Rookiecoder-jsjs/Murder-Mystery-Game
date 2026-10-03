import { Button, Picker, ScrollView, Text, Textarea, View } from '@tarojs/components'
import { useMemo, useState } from 'react'
import { ClueCard, PortraitFrame } from '@/components'
import { useGame } from '@/store/game-context'
import { showError } from '@/utils/feedback'
import './DiscussionPanel.scss'

export function DiscussionPanel() {
  const { state, speak, returnToInvestigation, startNextRound, startVoting } = useGame()
  const quickModeNeedsAnotherRound = state.mode === 'quick' && state.round < state.maxRounds
  const [message, setMessage] = useState('')
  const [targetIndex, setTargetIndex] = useState(0)
  const [evidenceIndex, setEvidenceIndex] = useState(0)
  const targets = state.characters.filter((c) => c.id !== state.player?.id)
  const evidence = [...state.clues, ...state.scenePublicClues]
  const portraits = useMemo(
    () => state.characters.map((item) => item.portrait_url || ''),
    [state.characters],
  )

  const submit = async () => {
    const trimmed = message.trim()
    if (!trimmed || state.isSpeaking) return
    setMessage('')
    try {
      await speak(trimmed, { target_id: targets[targetIndex - 1]?.id, presented_clue_ids: evidence[evidenceIndex - 1] ? [evidence[evidenceIndex - 1].id] : [] })
      setEvidenceIndex(0)
    } catch (error) {
      setMessage(trimmed)
      showError(error)
    }
  }

  const backToSearch = async () => {
    try {
      await returnToInvestigation()
    } catch (error) {
      showError(error)
    }
  }

  const enterVoting = async () => {
    try {
      await startVoting()
    } catch (error) {
      showError(error)
    }
  }

  const advanceRound = async () => {
    try { await startNextRound() }
    catch (error) { showError(error) }
  }

  return (
    <View className='game-panel discussion-panel'>
      <View className='game-panel__heading'>
        <Text className='section-kicker'>ACT III · TESTIMONY</Text>
        <Text className='section-title'>证言对照</Text>
        <Text className='section-desc'>第 {state.round} 轮讨论。把说辞与证据并排看，矛盾往往藏在看似无关的细节里。</Text>
      </View>

      <ScrollView className='discussion-panel__roster' scrollX enhanced showScrollbar={false}>
        <View className='discussion-panel__roster-row'>
          {state.characters.map((character) => (
            <View key={character.id} className='discussion-panel__roster-item'>
              <PortraitFrame
                name={character.name}
                src={character.portrait_url}
                size='card'
                previewGroup={portraits}
              />
              {character.id === state.player?.id && <View className='discussion-panel__you-stamp'>你</View>}
            </View>
          ))}
        </View>
      </ScrollView>

      {state.clues.length > 0 && (
        <View className='discussion-panel__evidence'>
          <View className='discussion-panel__section-head'>
            <Text className='field-label'>手边证据</Text>
            <Text>讨论时可引用</Text>
          </View>
          <ScrollView scrollX enhanced showScrollbar={false}>
            <View className='discussion-panel__evidence-row'>
              {state.clues.slice(0, 4).map((clue) => (
                <View key={clue.id} className='discussion-panel__evidence-card'>
                  <ClueCard clue={clue} />
                </View>
              ))}
            </View>
          </ScrollView>
        </View>
      )}

      <View className='discussion-panel__section-head discussion-panel__testimony-head'>
        <Text className='field-label'>口供记录</Text>
        <Text>{state.discussionHistory.length} 条</Text>
      </View>

      <View className='discussion-panel__messages'>
        {state.discussionHistory.length === 0 ? (
          <View className='paper-card empty-state'>还没有人正式发言，由你抛出第一个问题吧</View>
        ) : state.discussionHistory.map((item, index) => {
          const character = state.characters.find((candidate) => candidate.name === item.speaker)
          const isPlayer = character?.id === state.player?.id || item.speaker === '你'
          return (
            <View key={`${item.speaker}-${index}`} className={`testimony ${isPlayer ? 'testimony--player' : ''}`}>
              {character ? (
                <PortraitFrame
                  name={character.name}
                  src={character.portrait_url}
                  size='thumb'
                  label=''
                  previewGroup={portraits}
                />
              ) : (
                <View className='testimony__unknown'>{item.speaker.slice(0, 1)}</View>
              )}
              <View className='testimony__sheet'>
                <View className='testimony__head'>
                  <Text>{item.speaker}</Text>
                  <Text>STATEMENT / {String(index + 1).padStart(2, '0')}</Text>
                </View>
                <Text className='testimony__content'>{item.message}</Text>
                {isPlayer && <View className='testimony__stamp'>本人陈述</View>}
              </View>
            </View>
          )
        })}

        {state.isSpeaking && (
          <View className='discussion-panel__thinking'>
            <View className='spin-mark' />
            <Text>其他人物正在权衡你的说辞……</Text>
          </View>
        )}
      </View>

      <View className='discussion-panel__composer paper-card'>
        <Text className='field-label'>提交你的推论或质问</Text>
        <Picker mode='selector' range={['全员讨论', ...targets.map((c) => c.name)]} value={targetIndex} onChange={(e) => setTargetIndex(Number(e.detail.value))} disabled={state.isSpeaking}>
          <View className='discussion-panel__choice'>询问：{targets[targetIndex - 1]?.name || '全员讨论'}</View>
        </Picker>
        <Picker mode='selector' range={['不出示证据', ...evidence.map((c) => c.title || c.content.slice(0, 24))]} value={evidenceIndex} onChange={(e) => setEvidenceIndex(Number(e.detail.value))} disabled={state.isSpeaking}>
          <View className='discussion-panel__choice'>证据：{evidence[evidenceIndex - 1]?.content.slice(0, 24) || '不出示'}</View>
        </Picker>
        <Textarea
          className='archive-textarea discussion-panel__textarea'
          value={message}
          maxlength={500}
          placeholder='引用线索、质问某人，或给出你的推论……'
          placeholderClass='archive-placeholder'
          onInput={(event) => setMessage(event.detail.value)}
        />
        <View className='discussion-panel__composer-foot'>
          <Text>{message.length} / 500</Text>
          <Button className='primary-button' disabled={!message.trim() || state.isSpeaking} onClick={submit}>
            {state.isSpeaking ? '等待回应' : '提交发言'}
          </Button>
        </View>
      </View>

      <View className='discussion-panel__footer'>
        <Button className='secondary-button' disabled={state.isSpeaking || state.isLoading} onClick={backToSearch}>补充调查</Button>
        {quickModeNeedsAnotherRound && <Button className='primary-button' disabled={state.isSpeaking || state.isLoading || !state.availableActions.includes('next_round')} onClick={advanceRound}>下一轮调查</Button>}
        {!quickModeNeedsAnotherRound && <Button className='danger-button' disabled={state.isSpeaking || state.isLoading || (state.mode === 'quick' && !state.availableActions.includes('vote'))} onClick={enterVoting}>
          {quickModeNeedsAnotherRound ? `还需 ${state.maxRounds - state.round} 轮` : state.mode === 'quick' && !state.availableActions.includes('vote') ? '先发表本轮推论' : '结束讨论 · 进入表决'}
        </Button>}
      </View>
    </View>
  )
}
