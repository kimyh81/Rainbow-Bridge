import { useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated, ImageBackground } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';

// 시트 톤 (이미지 배경 위 — 파스텔 라벤더)
const C = {
  ink: '#5B4E75', inkM: '#8A7D9E', inkS: '#A89FBC',
  paper: '#FBF7FB', violet: '#8A5CB0', line: '#E5DCF0',
};

// 이미지 하늘 위 반짝이는 별 살짝 (생기)
function Star({ top, left, size, delay }) {
  const op = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(op, { toValue: 0.9, duration: 1400, delay, useNativeDriver: true }),
        Animated.timing(op, { toValue: 0, duration: 1400, useNativeDriver: true }),
      ]),
    ).start();
  }, []);
  return (
    <Animated.View
      style={{
        position: 'absolute', top, left, width: size, height: size,
        borderRadius: size / 2, backgroundColor: '#fff', opacity: op,
      }}
    />
  );
}

export default function Onboard() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  // 상단 하늘 영역에 별 몇 개 (이미지 위 오버레이)
  const stars = useRef(
    Array.from({ length: 14 }).map(() => ({
      top: Math.random() * 220 + 20,
      left: Math.random() * 340 + 10,
      size: Math.random() * 2 + 1.5,
      delay: Math.random() * 1800,
    })),
  ).current;

  return (
    <ImageBackground
      source={require('../../assets/onboard_bg.png')}
      style={s.bg}
      resizeMode="cover"
    >
      <SafeAreaView style={s.safe}>
        {/* 별 반짝임 (이미지 하늘 위) */}
        {stars.map((st, i) => (
          <Star key={i} {...st} />
        ))}

        {/* 하단 시트 */}
        <View style={[s.sheet, { paddingBottom: 36 + insets.bottom }]}>
          <View style={s.handle} />
          <View style={s.chip}>
            <Text style={s.chipTxt}>🌈 Rainbow Bridge</Text>
          </View>
          <Text style={s.h1}>아이가 강아지별로{'\n'}이사를 준비하고 있어요</Text>
          <Text style={s.sub}>남은 시간을 함께 채우고,{'\n'}이별 후에도 곁에 있을게요.</Text>

          <TouchableOpacity activeOpacity={0.85} style={s.btnShadow} onPress={() => router.push('/(auth)/register')}>
            <LinearGradient colors={['#8A5CB0', '#B89ACA', '#C8A8D8']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.btnMain}>
              <Text style={s.btnMainTxt}>시작하기</Text>
            </LinearGradient>
          </TouchableOpacity>

          <TouchableOpacity activeOpacity={0.7} style={s.btnOut} onPress={() => router.push('/(auth)/login')}>
            <Text style={s.btnOutTxt}>이미 계정이 있어요</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </ImageBackground>
  );
}

const s = StyleSheet.create({
  bg: { flex: 1 },
  safe: { flex: 1, justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: 'rgba(248,242,255,0.74)',
    borderRadius: 30,
    marginHorizontal: 12,
    marginBottom: 16,
    paddingHorizontal: 28,
    paddingTop: 16,
    paddingBottom: 36,  /* 기본값 — insets.bottom이 inline으로 덮어씀 */
    borderWidth: 1.5,
    borderColor: 'rgba(180,140,210,0.35)',
    shadowColor: '#503C5A',
    shadowOffset: { width: 0, height: -6 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 16,
  },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: '#E4D8E4', alignSelf: 'center', marginBottom: 12 },
  chip: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(148,118,168,0.1)',
    paddingHorizontal: 13, paddingVertical: 5, borderRadius: 20, marginBottom: 10,
  },
  chipTxt: { fontSize: 11, fontWeight: '500', letterSpacing: 1, color: C.violet },
  h1: { fontSize: 24, fontWeight: '700', color: C.ink, lineHeight: 33, marginBottom: 7 },
  sub: { fontSize: 13, color: C.inkM, lineHeight: 21, marginBottom: 18 },
  btnShadow: {
    marginBottom: 10, borderRadius: 18,
    shadowColor: C.violet, shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.4, shadowRadius: 18, elevation: 8,
  },
  btnMain: { paddingVertical: 15, borderRadius: 18, alignItems: 'center' },
  btnMainTxt: { color: '#fff', fontSize: 15, fontWeight: '500', letterSpacing: 0.3 },
  btnOut: { paddingVertical: 13, borderRadius: 18, alignItems: 'center', borderWidth: 1.5, borderColor: 'rgba(138,92,176,0.25)' },
  btnOutTxt: { color: C.ink, fontSize: 14, fontWeight: '500' },
});
