import { Text, View } from '@tarojs/components'
import { PortraitFrame } from './PortraitFrame'
import type { CharacterInfo } from '@/types/game'
import './CharacterDossier.scss'

interface CharacterDossierProps {
  character: CharacterInfo
  statement?: string
  isPlayer?: boolean
  portraitGroup?: string[]
}

export function CharacterDossier({
  character,
  statement,
  isPlayer = false,
  portraitGroup,
}: CharacterDossierProps) {
  return (
    <View className='character-dossier paper-card'>
      <View className='character-dossier__portrait'>
        <PortraitFrame
          name={character.name}
          src={character.portrait_url}
          size='card'
          previewGroup={portraitGroup}
        />
      </View>
      <View className='character-dossier__body'>
        <View className='character-dossier__name-row'>
          <Text className='character-dossier__name'>{character.name}</Text>
          {isPlayer && <Text className='character-dossier__you'>你</Text>}
        </View>
        <Text className='character-dossier__identity'>{character.public_identity}</Text>
        <Text className='character-dossier__appearance'>{character.appearance}</Text>
        {statement && (
          <View className='character-dossier__statement'>
            <Text>口供摘录</Text>
            <Text>{statement}</Text>
          </View>
        )}
      </View>
    </View>
  )
}
