import { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, TextInput,
  StyleSheet, ScrollView, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import SafetyModal from '@/components/SafetyModal';
import Button from '@/components/Button';
import { postEmotion } from '@/api/emotions';
import { COLORS } from '@/constants/colors';

const MOODS = [
  { emoji: '😊', label: '괜찮아요',      score: 9 },
  { emoji: '😔', label: '슬퍼요',        score: 6 },
  { emoji: '😢', label: '많이 힘들어요',  score: 3 },
  { emoji: '😰', label: '너무 힘들어요',  score: 1 },
  { emoji: '😶', label: '잘 모르겠어요',  score: 5 },
];

const RISK_MOODS = ['너무 힘들어요'];

export default function EmotionScreen() {
  const router = useRouter();
  const [selectedMood, setSelectedMood] = useState(null);
  const [note, setNote] = useState('');
  const [safetyOpen, setSafetyOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [petName, setPetName] = useState('소중한 친구');

  useEffect(() => {
    AsyncStorage.getItem('pet_name').then((v) => v && setPetName(v));
  }, []);

  async function handleSubmit() {
    if (!selectedMood) {
      setError('오늘 기분을 선택해주세요.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const moodScore = MOODS.find((m) => m.label === selectedMood)?.score ?? 5;
      const response = await postEmotion({ pet_id: petId, score: moodScore, note });

      if (response.risk_level >= 2 || RISK_MOODS.includes(selectedMood)) {
        setSafetyOpen(true);
        return;
      }
      router.push('/(app)/mission');
    } catch {
      if (RISK_MOODS.includes(selectedMood)) {
        setSafetyOpen(true);
        return;
      }
      router.push('/(app)/mission');
    } finally {
      setLoading(false);
    }
  }

  return (
    <LinearGradient
      colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']}
      locations={[0, 0.35, 0.6, 1]}
      style={styles.gradient}
    >
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={true}
      >
        <Text style={styles.title}>오늘 기분이 어떠세요?</Text>
        <Text style={styles.subtitle}>솔직하게 선택해주세요.</Text>

        <View style={styles.moodList}>
          {MOODS.map(({ emoji, label }) => {
            const selected = selectedMood === label;
            return (
              <TouchableOpacity
                key={label}
                onPress={() => setSelectedMood(label)}
                style={[styles.moodBtn, selected && styles.moodBtnSelected]}
                activeOpacity={0.8}
              >
                <Text style={styles.moodEmoji}>{emoji}</Text>
                <Text style={[styles.moodLabel, selected && styles.moodLabelSelected]}>
                  {label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <TextInput
          style={styles.noteInput}
          value={note}
          onChangeText={setNote}
          placeholder="오늘 있었던 일을 적어도 좋아요. (선택)"
          placeholderTextColor={COLORS.textLight}
          multiline
          numberOfLines={3}
          textAlignVertical="top"
          selectionColor={COLORS.cta}
          cursorColor={COLORS.cta}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Button
          onPress={handleSubmit}
          loading={loading}
          variant="primary"
          style={styles.btn}
        >
          기록하기
        </Button>
      </ScrollView>

      <SafetyModal
        isOpen={safetyOpen}
        onClose={() => {
          setSafetyOpen(false);
          router.push('/(app)/message');
        }}
      />
      </KeyboardAvoidingView>
    </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 24, paddingVertical: 36 },
  title: { fontSize: 22, fontWeight: '700', color: '#5B4E75', textAlign: 'center', marginBottom: 6 },
  subtitle: { fontSize: 14, color: '#8A7D9E', textAlign: 'center', marginBottom: 28 },
  moodList: { gap: 10, marginBottom: 24 },
  moodBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    paddingHorizontal: 18,
    paddingVertical: 16,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: COLORS.divider,
    backgroundColor: COLORS.white,
    shadowColor: '#C5B8BE',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 1,
  },
  moodBtnSelected: {
    borderColor: COLORS.selectedBorder,
    backgroundColor: '#FBF1F3',
    shadowOpacity: 0.14,
    elevation: 2,
  },
  moodEmoji: { fontSize: 28 },
  moodLabel: { fontSize: 15, color: COLORS.textSecondary, fontWeight: '500' },
  moodLabelSelected: { color: COLORS.selectedText, fontWeight: '700' },
  noteInput: {
    backgroundColor: COLORS.white,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 14,
    color: COLORS.textPrimary,
    borderWidth: 1.5,
    borderColor: COLORS.divider,
    minHeight: 90,
    marginBottom: 16,
  },
  error: { color: COLORS.danger, fontSize: 13, textAlign: 'center', marginBottom: 10 },
  btn: {},
});
