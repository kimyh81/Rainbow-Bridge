import { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Alert } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchRecoveryGate } from '@/utils/recovery';
import { iga } from '@/utils/josa';

// 선물 상태: 'ready'(받을 수 있음) | 'waiting'(곧 도착) | 'locked'(준비 중)
function GiftCard({ emoji, title, desc, state, actionLabel, onPress }) {
  const disabled = state !== 'ready';
  return (
    <Pressable
      style={({ pressed }) => [
        styles.giftCard,
        state === 'ready' && styles.giftCardReady,
        disabled && styles.giftCardDim,
        pressed && !disabled && { opacity: 0.85 },
      ]}
      onPress={() => !disabled && onPress?.()}
      disabled={disabled}
    >
      <Text style={[styles.giftEmoji, disabled && styles.giftEmojiDim]}>{emoji}</Text>
      <Text style={styles.giftTitle}>{title}</Text>
      <Text style={styles.giftDesc}>{desc}</Text>
      <View style={[
        styles.giftBtn,
        state === 'ready' && styles.giftBtnReady,
        state === 'waiting' && styles.giftBtnWaiting,
      ]}>
        <Text style={[styles.giftBtnText, state === 'ready' && styles.giftBtnTextReady]}>
          {actionLabel}
        </Text>
      </View>
    </Pressable>
  );
}

export default function GiftScreen() {
  const router = useRouter();
  const [petName, setPetName] = useState('소중한 친구');
  const [gateStatus, setGateStatus] = useState('checking');
  const [hasVideo, setHasVideo] = useState(false);
  const [hasLetter, setHasLetter] = useState(false);
  const [hasGif, setHasGif] = useState(false);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  async function load() {
    const [name, video, letter, gif, petId] = await Promise.all([
      AsyncStorage.getItem('pet_name'),
      AsyncStorage.getItem('pet_video_url'),
      AsyncStorage.getItem('message_content'),
      AsyncStorage.getItem('pet_gif_url'),
      AsyncStorage.getItem('pet_id'),
    ]);
    if (name) setPetName(name);
    setHasVideo(!!video);
    setHasLetter(!!letter);
    setHasGif(!!gif);
    const { gateStatus: gs } = await fetchRecoveryGate(petId);
    setGateStatus(gs);
  }

  const letterReady = gateStatus === 'teaser' || gateStatus === 'open';
  const firstPersonReady = gateStatus === 'open';
  const canPackage = hasLetter || hasVideo;

  // ── 추억 패키지 내보내기 ──
  // expo-file-system·expo-sharing은 네이티브 모듈이라 새 빌드에만 존재.
  // OTA 빌드에서 최상단 import하면 로드 시점에 크래시 → 함수 안에서 지연 로딩.
  function loadFileModules() {
    // 네이티브 모듈 미존재 시 require 단계에서 throw → 호출부 try/catch가 처리
    return {
      FileSystem: require('expo-file-system/legacy'),
      Sharing: require('expo-sharing'),
    };
  }

  async function exportLetter() {
    const content = await AsyncStorage.getItem('message_content');
    if (!content) {
      Alert.alert('아직 편지가 없어요', '먼저 추모 편지를 받아보세요.');
      return;
    }
    try {
      const { FileSystem, Sharing } = loadFileModules();
      const safeName = (petName || '추모').replace(/[\\/:*?"<>|]/g, '');
      const fileUri = `${FileSystem.documentDirectory}${safeName}_추모편지.txt`;
      await FileSystem.writeAsStringAsync(fileUri, content, {
        encoding: FileSystem.EncodingType.UTF8,
      });
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(fileUri, { mimeType: 'text/plain', dialogTitle: '추모 편지 저장' });
      }
    } catch {
      Alert.alert('저장 기능 준비 중', '추억 패키지 저장은 다음 앱 업데이트(새 빌드)부터 쓸 수 있어요.');
    }
  }

  async function exportGif() {
    const url = await AsyncStorage.getItem('pet_gif_url');
    if (!url) {
      Alert.alert('아직 숨쉬는 사진이 없어요', '조금 더 함께하면 도착할 거예요.');
      return;
    }
    try {
      const { FileSystem, Sharing } = loadFileModules();
      const safeName = (petName || '추모').replace(/[\\/:*?"<>|]/g, '');
      const fileUri = `${FileSystem.documentDirectory}${safeName}_숨쉬는사진.gif`;
      const { uri } = await FileSystem.downloadAsync(url, fileUri);
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: 'image/gif', dialogTitle: '숨쉬는 사진 저장' });
      }
    } catch {
      Alert.alert('저장 기능 준비 중', '숨쉬는 사진 저장은 다음 앱 업데이트(새 빌드)부터 쓸 수 있어요.');
    }
  }

  async function exportVideo() {
    const url = await AsyncStorage.getItem('pet_video_url');
    if (!url) {
      Alert.alert('아직 영상이 없어요', '추모 영상을 먼저 만들어주세요.');
      return;
    }
    try {
      const { FileSystem, Sharing } = loadFileModules();
      const safeName = (petName || '추모').replace(/[\\/:*?"<>|]/g, '');
      const fileUri = `${FileSystem.documentDirectory}${safeName}_추모영상.mp4`;
      const { uri } = await FileSystem.downloadAsync(url, fileUri);
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: 'video/mp4', dialogTitle: '추모 영상 저장' });
      }
    } catch {
      Alert.alert('저장 기능 준비 중', '추억 패키지 저장은 다음 앱 업데이트(새 빌드)부터 쓸 수 있어요.');
    }
  }

  function handlePackage() {
    const buttons = [];
    if (hasLetter) buttons.push({ text: '✉️ 편지 저장', onPress: exportLetter });
    if (hasVideo) buttons.push({ text: '🎬 영상 저장 (MP4)', onPress: exportVideo });
    if (hasGif) buttons.push({ text: '✨ 숨쉬는 사진 저장', onPress: exportGif });
    buttons.push({ text: '취소', style: 'cancel' });
    Alert.alert(
      '추억 패키지 내보내기',
      '간직하고 싶은 추억을 기기에 저장하거나 공유할 수 있어요.',
      buttons
    );
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
          <Text style={styles.title}>🎁 {petName}의 선물함</Text>
          <Text style={styles.subtitle}>
            회복 여정을 함께 걸으며{'\n'}하나씩 도착하는 선물들이에요.
          </Text>

          <View style={styles.grid}>
            {/* 위로 편지 (3인칭) */}
            <GiftCard
              emoji="✉️"
              title="위로 편지"
              desc={letterReady ? '도착했어요' : '조금 더 회복하면 도착해요'}
              state={letterReady ? 'ready' : 'waiting'}
              actionLabel={letterReady ? '열어보기' : '기다리는 중'}
              onPress={() => router.push('/(app)/message')}
            />

            {/* 별에서 온 편지 (1인칭) */}
            <GiftCard
              emoji="🌠"
              title="별에서 온 편지"
              desc={firstPersonReady ? `${petName}${iga(petName)} 직접 전하는 말` : '마음이 더 단단해지면 열려요'}
              state={firstPersonReady ? 'ready' : 'locked'}
              actionLabel={firstPersonReady ? '열어보기' : '준비 중'}
              onPress={() => router.push('/(app)/message?mode=first')}
            />

            {/* 숨쉬는 사진 (추모 영상 + GIF) */}
            <GiftCard
              emoji="🎞️"
              title="숨쉬는 사진"
              desc={hasVideo ? '아이의 살며시 움직이는 순간이에요' : '슬라이드쇼 미션을 완료하면 도착해요'}
              state={hasVideo ? 'ready' : 'locked'}
              actionLabel={hasVideo ? '열어보기' : '준비 중'}
              onPress={() => router.push('/(app)/media')}
            />

            {/* 추억 패키지 */}
            <GiftCard
              emoji="📦"
              title="추억 패키지"
              desc={canPackage ? '편지·영상을 저장해요' : '여정이 쌓이면 함께 보관해요'}
              state={canPackage ? 'ready' : 'locked'}
              actionLabel={canPackage ? '내보내기' : '준비 중'}
              onPress={handlePackage}
            />
          </View>

          <View style={styles.notice}>
            <Text style={styles.noticeText}>
              💡 선물은 감정 체크인·미션으로 회복 흐름이 확인되면{'\n'}순서대로 도착해요. 천천히 괜찮아요 🐾
            </Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 18, paddingVertical: 24, paddingBottom: 48 },

  title: { fontSize: 22, fontWeight: '800', color: '#5B4E75', textAlign: 'center', marginBottom: 8 },
  subtitle: { fontSize: 13, color: '#8A7D9E', textAlign: 'center', lineHeight: 20, marginBottom: 24 },

  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12 },
  giftCard: {
    width: '48%',
    backgroundColor: 'rgba(255,255,255,0.7)',
    borderRadius: 20, padding: 18, marginBottom: 0,
    borderWidth: 1.5, borderColor: '#E5DCF0',
    alignItems: 'center',
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08, shadowRadius: 8, elevation: 2,
  },
  giftCardReady: { backgroundColor: '#FFFFFF', borderColor: '#C9B8E8' },
  giftCardDim: { opacity: 0.78 },
  giftEmoji: { fontSize: 34, marginBottom: 8 },
  giftEmojiDim: { opacity: 0.55 },
  giftTitle: { fontSize: 15, fontWeight: '800', color: '#5B4E75', textAlign: 'center' },
  giftDesc: { fontSize: 11.5, color: '#8A7D9E', textAlign: 'center', marginTop: 5, lineHeight: 16, minHeight: 32 },

  giftBtn: {
    marginTop: 12, paddingVertical: 8, paddingHorizontal: 14,
    borderRadius: 12, backgroundColor: '#F0EAF5',
  },
  giftBtnReady: { backgroundColor: '#C4A8D8' },
  giftBtnWaiting: { backgroundColor: '#EDE5FA' },
  giftBtnText: { fontSize: 12, fontWeight: '700', color: '#A89FBC' },
  giftBtnTextReady: { color: '#FFFFFF' },

  notice: {
    marginTop: 22, backgroundColor: 'rgba(255,255,255,0.5)',
    borderRadius: 16, padding: 16,
    borderWidth: 1, borderColor: 'rgba(196,168,216,0.3)',
  },
  noticeText: { fontSize: 12, color: '#76698F', textAlign: 'center', lineHeight: 19 },
});
