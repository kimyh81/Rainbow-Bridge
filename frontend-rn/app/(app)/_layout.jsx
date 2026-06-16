import { useState, useEffect } from 'react';
import { Stack, router, usePathname } from 'expo-router';
import { Pressable, Text, View, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS } from '@/constants/colors';

export async function doLogout() {
  try {
    await AsyncStorage.multiRemove([
      'access_token', 'pet_id', 'pet_name', 'pet_species',
      'bucketlist_items', 'diary_entries', 'caller_name',
      'pet_photos', 'recovery_cache', 'pet_farewell_date', 'memorial_mode',
      'pet_guardian_title', 'pet_gender', 'pet_start_date',
      // 미디어·메시지 관련 키 — 재로그인 시 이전 데이터 잔존 방지
      'pet_video_url', 'pet_voiced_url', 'pet_gif_url', 'pet_video_asset_id', 'pet_photo_url',
      'message_content', 'message_id', 'message_tone', 'tts_done',
    ]);
  } catch {}
  router.replace('/(auth)/login');
}

// 모든 (app) 화면 하단에 깔리는 공용 바
const TABS = [
  { key: 'home', emoji: '🏠', label: '홈', path: '/home', route: '/(app)/home' },
  { key: 'health', emoji: '🏃', label: '삼성헬스', path: '/health', route: '/(app)/health' },
  { key: 'timeline', emoji: '🌿', label: '타임라인', path: '/timeline', route: '/(app)/timeline' },
  { key: 'report', emoji: '📊', label: '리포트', path: '/report', route: '/(app)/report' },
];

// 하단 바를 숨길 화면 — 추모 편지(별에서 온 편지)는 다크 몰입형이라 바가 어색함
const BAR_HIDDEN_PATHS = ['/message'];

function BottomBar() {
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const [memorialMode, setMemorialMode] = useState(false);

  // 화면 이동 때마다 모드 갱신 (이별 전: 3개 / 이별 후: 5개)
  useEffect(() => {
    AsyncStorage.getItem('memorial_mode').then((v) => setMemorialMode(v === 'true'));
  }, [pathname]);

  // 추모 편지 등 몰입형 화면에선 하단 바 숨김
  if (BAR_HIDDEN_PATHS.includes(pathname)) return null;

  // 추모 타임라인·회복 리포트는 이별 후에만 노출
  const tabs = memorialMode
    ? TABS
    : TABS.filter((t) => t.key === 'home' || t.key === 'health');

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 10) }]}>
      {tabs.map((t) => {
        const active = pathname === t.path;
        return (
          <Pressable
            key={t.key}
            style={styles.item}
            onPress={() => router.navigate(t.route)}
            hitSlop={8}
          >
            <Text style={[styles.emoji, !active && styles.dim]}>{t.emoji}</Text>
            <Text style={[styles.label, active && styles.labelActive]}>{t.label}</Text>
          </Pressable>
        );
      })}

      <Pressable style={styles.item} onPress={doLogout} hitSlop={8}>
        <Text style={[styles.emoji, styles.dim]}>🚪</Text>
        <Text style={[styles.label, styles.logout]}>로그아웃</Text>
      </Pressable>
    </View>
  );
}

export default function AppLayout() {
  return (
    <View style={{ flex: 1 }}>
      <View style={{ flex: 1 }}>
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: COLORS.background },
            headerTintColor: COLORS.textPrimary,
            headerTitleStyle: { fontWeight: '600', fontSize: 17 },
            headerShadowVisible: false,
            headerBackTitle: '뒤로',
            contentStyle: { backgroundColor: COLORS.background },
          }}
        >
          <Stack.Screen name="home"           options={{ title: '홈', headerShown: false }} />
          <Stack.Screen name="profile"        options={{ title: '프로필 등록' }} />
          <Stack.Screen name="farewell"       options={{ title: '이별 안내' }} />
          <Stack.Screen name="funeral"        options={{ title: '장례 안내' }} />
          <Stack.Screen name="mission"        options={{ title: '오늘의 미션', headerShown: false }} />
          <Stack.Screen name="timeline"       options={{ title: '추모 타임라인' }} />
          <Stack.Screen name="report"         options={{ title: '회복 리포트', headerShown: false }} />
          <Stack.Screen name="emotion"        options={{ title: '감정 체크인' }} />
          <Stack.Screen name="message"        options={{ title: '추모 메시지', headerShown: false, contentStyle: { backgroundColor: '#241e32' } }} />
          <Stack.Screen name="gift"           options={{ title: '선물함' }} />
          <Stack.Screen name="tts"            options={{ title: 'TTS 음성' }} />
          <Stack.Screen name="bucketlist"     options={{ title: '버킷리스트' }} />
          <Stack.Screen name="diary"          options={{ title: '일기 & 추억 메모' }} />
          <Stack.Screen name="memories"       options={{ title: '추억 입력' }} />
          <Stack.Screen name="memories_diary" options={{ title: '추억 메모' }} />
          <Stack.Screen name="photos"         options={{ title: '사진 기록' }} />
          <Stack.Screen name="media"          options={{ title: '추모 영상 만들기' }} />
          <Stack.Screen name="health"         options={{ title: '삼성헬스 연동' }} />
        </Stack>
      </View>
      <BottomBar />
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#EDE5F5',
    paddingTop: 8,
    paddingHorizontal: 8,
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 8,
  },
  item: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 4, paddingHorizontal: 2 },
  emoji: { fontSize: 20, marginBottom: 3 },
  dim: { opacity: 0.55 },
  label: { fontSize: 10, color: '#A89FBC', fontWeight: '600' },
  labelActive: { color: '#7A5CA8', fontWeight: '800' },
  logout: { color: '#E57373' },
});
