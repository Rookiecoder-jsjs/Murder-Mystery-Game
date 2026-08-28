import { Button, ScrollView, Text, View } from '@tarojs/components'
import { PortraitFrame } from './PortraitFrame'
import type { CharacterInfo } from '@/types/game'
import './SuspectPicker.scss'

interface SuspectPickerProps {
  visible: boolean
  title: string
  note: string
  characters: CharacterInfo[]
  selectedId?: string
  confirmText: string
  dangerous?: boolean
  loading?: boolean
  onSelect: (id: string) => void
  onClose: () => void
  onConfirm: () => void
}

export function SuspectPicker({
  visible,
  title,
  note,
  characters,
  selectedId,
  confirmText,
  dangerous = false,
  loading = false,
  onSelect,
  onClose,
  onConfirm,
}: SuspectPickerProps) {
  if (!visible) return null
  const portraits = characters.map((item) => item.portrait_url || '')

  return (
    <View className='suspect-picker'>
      <View className='suspect-picker__scrim' onClick={onClose} />
      <View className='suspect-picker__sheet'>
        <View className='suspect-picker__handle' />
        <Text className='suspect-picker__kicker'>SUSPECT ARCHIVE</Text>
        <Text className='suspect-picker__title'>{title}</Text>
        <Text className='suspect-picker__note'>{note}</Text>
        <ScrollView className='suspect-picker__scroll' scrollY>
          <View className='suspect-picker__grid'>
            {characters.map((character) => (
              <View
                key={character.id}
                className={`suspect-picker__item ${selectedId === character.id ? 'suspect-picker__item--selected' : ''}`}
                onClick={() => onSelect(character.id)}
              >
                <PortraitFrame
                  name={character.name}
                  src={character.portrait_url}
                  size='poster'
                  label=''
                  previewGroup={portraits}
                />
                <Text className='suspect-picker__name'>{character.name}</Text>
                <Text className='suspect-picker__identity'>{character.public_identity}</Text>
                {selectedId === character.id && <View className='suspect-picker__stamp'>选中</View>}
              </View>
            ))}
          </View>
        </ScrollView>
        <View className='suspect-picker__actions'>
          <Button className='secondary-button' onClick={onClose}>再想想</Button>
          <Button
            className={dangerous ? 'danger-button' : 'primary-button'}
            disabled={!selectedId || loading}
            onClick={onConfirm}
          >
            {loading ? '正在落印…' : confirmText}
          </Button>
        </View>
        <View className='safe-bottom' />
      </View>
    </View>
  )
}
