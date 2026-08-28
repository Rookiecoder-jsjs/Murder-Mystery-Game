import { Button, Text, Textarea, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'
import { CharacterDossier, PortraitFrame } from '@/components'
import { useGame } from '@/store/game-context'
import { showError } from '@/utils/feedback'
import './IntroductionPanel.scss'

export function IntroductionPanel() {
  const { state, introduce, nextPhase } = useGame()
  const [message, setMessage] = useState('')
  const hasIntroductions = state.introductions.length > 0

  useEffect(() => {
    if (state.player && !message) {
      setMessage(`大家好，我是${state.player.name}，${state.player.public_identity}。`)
    }
  }, [state.player, message])

  const portraitGroup = useMemo(
    () => state.characters.map((item) => item.portrait_url || ''),
    [state.characters],
  )

  if (!state.player) return null

  const submitIntroduction = async () => {
    try {
      await introduce(message.trim())
    } catch (error) {
      showError(error)
    }
  }

  const enterInvestigation = async () => {
    try {
      await nextPhase()
    } catch (error) {
      showError(error)
    }
  }

  if (hasIntroductions) {
    return (
      <View className='game-panel intro-panel'>
        <View className='game-panel__heading'>
          <Text className='section-kicker'>ACT I · INTRODUCTION</Text>
          <Text className='section-title'>人物已悉数入场</Text>
          <Text className='section-desc'>第一轮说辞已经归档。注意他们刻意强调、或有意省略的细节。</Text>
        </View>

        <View className='intro-panel__dossiers'>
          {state.characters.map((character) => {
            const statement = state.introductions.find((item) => item.speaker === character.name)?.message
            return (
              <CharacterDossier
                key={character.id}
                character={character}
                statement={statement}
                isPlayer={character.id === state.player?.id}
                portraitGroup={portraitGroup}
              />
            )
          })}
        </View>

        <View className='intro-panel__next paper-card'>
          <Text>所有口供已编号归档</Text>
          <Text>下一步将进入案发现场，你可以搜查证物并逐步建立推论。</Text>
          <Button className='primary-button' onClick={enterInvestigation}>进入现场 · 开始调查</Button>
        </View>
      </View>
    )
  }

  return (
    <View className='game-panel intro-panel'>
      <View className='game-panel__heading'>
        <Text className='section-kicker'>ACT I · INTRODUCTION</Text>
        <Text className='section-title'>你的角色档案</Text>
        <Text className='section-desc'>先看清自己的身份与外貌，再决定以怎样的方式走入众人的视线。</Text>
      </View>

      <View className='intro-panel__hero paper-card'>
        <PortraitFrame
          name={state.player.name}
          src={state.player.portrait_url}
          size='hero'
          previewGroup={portraitGroup}
        />
        <View className='intro-panel__identity'>
          <Text className='intro-panel__file-no'>PERSONNEL FILE / {state.player.id.toUpperCase()}</Text>
          <View className='intro-panel__name-row'>
            <Text>{state.player.name}</Text>
            <Text>你</Text>
          </View>
          <Text className='intro-panel__job'>{state.player.public_identity}</Text>
          <Text className='intro-panel__appearance'>{state.player.appearance}</Text>
          <Text className='intro-panel__private'>此页只属于你。人物照片可点击查看全貌。</Text>
        </View>
      </View>

      <View className='intro-panel__form paper-card'>
        <Text className='field-label'>你的自我介绍</Text>
        <Text className='intro-panel__form-note'>默认介绍可以直接使用，也可以改成更符合人物气质的开场白。</Text>
        <Textarea
          className='archive-textarea intro-panel__textarea'
          value={message}
          maxlength={500}
          placeholder='写下你的开场白……'
          placeholderClass='archive-placeholder'
          onInput={(event) => setMessage(event.detail.value)}
        />
        <View className='intro-panel__form-foot'>
          <Text>{message.length} / 500</Text>
          <Button className='primary-button' disabled={!message.trim()} onClick={submitIntroduction}>
            开始自我介绍
          </Button>
        </View>
      </View>

      <View className='intro-panel__roster'>
        <Text className='field-label'>即将与你同台的人</Text>
        <View className='intro-panel__roster-row'>
          {state.characters.filter((item) => item.id !== state.player?.id).map((character) => (
            <PortraitFrame
              key={character.id}
              name={character.name}
              src={character.portrait_url}
              size='card'
              previewGroup={portraitGroup}
            />
          ))}
        </View>
      </View>
    </View>
  )
}
