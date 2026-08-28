import { Button, ScrollView, Text, Textarea, View } from '@tarojs/components'
import { useMemo, useState } from 'react'
import { ClueCard, PortraitFrame } from '@/components'
import { useGame } from '@/store/game-context'
import { showError } from '@/utils/feedback'
import './DiscussionPanel.scss'

export function DiscussionPanel() {
  const { state, speak, returnToInvestigation, startVoting } = useGame()
  const [message, setMessage] = useState('')
  const portraits = useMemo(
    () => state.characters.map((item) => item.portrait_url || ''),
    [state.characters],
  )

  const submit = async () => {
    const trimmed = message.trim()
    if (!trimmed || state.isSpeaking) return
    setMessage('')
    try {
      await speak(trimmed)
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
        <Button className='secondary-button' onClick={backToSearch}>返回搜证</Button>
        <Button className='danger-button' onClick={enterVoting}>结束讨论 · 进入表决</Button>
      </View>
    </View>
  )
}
