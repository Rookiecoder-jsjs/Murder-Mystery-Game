import Taro from '@tarojs/taro'
import { Button, Text, View } from '@tarojs/components'
import { useMemo, useState } from 'react'
import { PortraitFrame } from '@/components'
import { useGame } from '@/store/game-context'
import { showError, showNotice } from '@/utils/feedback'
import './VotingPanel.scss'

export function VotingPanel() {
  const { state, vote, returnToInvestigation } = useGame()
  const [selectedId, setSelectedId] = useState('')
  const [resultText, setResultText] = useState('')
  const suspects = useMemo(
    () => state.characters.filter((item) => item.id !== state.player?.id),
    [state.characters, state.player?.id],
  )
  const portraits = suspects.map((item) => item.portrait_url || '')
  const selected = suspects.find((item) => item.id === selectedId)

  const submitVote = async () => {
    if (!selected) return
    const modal = await Taro.showModal({
      title: `把票投给 ${selected.name}？`,
      content: '表决将与其他人物的判断一起封存。确认后无法单独更改。',
      confirmText: '确认投票',
      confirmColor: '#9d3328',
    })
    if (!modal.confirm) return

    try {
      const result = await vote(selected.name)
      setResultText(result.result)
      if (result.game_ended && state.gameId) {
        Taro.redirectTo({ url: `/pages/reveal/index?gameId=${state.gameId}` })
      } else {
        showNotice(result.result || '投票已封存')
      }
    } catch (error) {
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

  return (
    <View className='game-panel voting-panel'>
      <View className='voting-panel__heading'>
        <Text className='section-kicker'>ACT IV · FINAL BALLOT</Text>
        <Text className='section-title'>嫌疑人表决</Text>
        <Text className='section-desc'>从人物海报中选定最终嫌疑人。回忆他们的身份、说辞，以及谁最需要让某条线索消失。</Text>
        <View className='voting-panel__seal'>绝密{`\n`}表决</View>
      </View>

      <View className='voting-panel__warning'>
        <Text>!</Text>
        <View>
          <Text>最后判断</Text>
          <Text>选中人物后仍可查看肖像全貌；点击底部按钮才会正式落票。</Text>
        </View>
      </View>

      <View className='voting-panel__grid'>
        {suspects.map((character, index) => (
          <View
            key={character.id}
            className={`voting-poster ${selectedId === character.id ? 'voting-poster--selected' : ''}`}
            onClick={() => setSelectedId(character.id)}
          >
            <Text className='voting-poster__no'>SUSPECT {String(index + 1).padStart(2, '0')}</Text>
            <PortraitFrame
              name={character.name}
              src={character.portrait_url}
              size='poster'
              label=''
              previewGroup={portraits}
            />
            <Text className='voting-poster__name'>{character.name}</Text>
            <Text className='voting-poster__identity'>{character.public_identity}</Text>
            {selectedId === character.id && <View className='voting-poster__stamp'>我的选择</View>}
          </View>
        ))}
      </View>

      {resultText && <View className='voting-panel__result paper-card'>{resultText}</View>}

      <View className='voting-panel__selection paper-card'>
        <Text>你的选票</Text>
        <Text>{selected ? `${selected.name} · ${selected.public_identity}` : '尚未选择嫌疑人'}</Text>
      </View>

      <View className='voting-panel__footer'>
        <Button className='secondary-button' onClick={backToSearch}>返回搜证</Button>
        <Button className='danger-button' disabled={!selected} onClick={submitVote}>
          {selected ? `投给 ${selected.name}` : '选择一名嫌疑人'}
        </Button>
      </View>
    </View>
  )
}
