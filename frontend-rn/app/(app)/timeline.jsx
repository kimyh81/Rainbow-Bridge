import { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Card from '@/components/Card';
import LoadingSpinner from '@/components/LoadingSpinner';
import { getTimeline } from '@/api/timeline';
import { mockTimeline } from '@/api/mock';
import { COLORS } from '@/constants/colors';
import { gwa } from '@/utils/josa';

const TYPE_META = {
  emotion: { emoji: '💭', label: '감정 기록' },
  message: { emoji: '💌', label: '추모 메시지' },
  mission: { emoji: '🌱', label: '미션 완료' },
  media:   { emoji: '🎞️', label: '추모 영상' },
};

function formatDate(str) {
  const d = new Date(str);
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}

export default function TimelineScreen() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [petName, setPetName] = useState('소중한 친구');

  useEffect(() => {
    AsyncStorage.getItem('pet_name').then((v) => v && setPetName(v));
    fetchTimeline();
  }, []);

  async function fetchTimeline() {
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const data = await getTimeline({ pet_id: petId });
      setItems(data);
    } catch {
      setItems(mockTimeline);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <LoadingSpinner message="추억을 불러오고 있어요..." />
        </SafeAreaView>
      </LinearGradient>
    );
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>추모 타임라인</Text>
        <Text style={styles.subtitle}>{petName}{gwa(petName)} 함께한 기억들이에요.</Text>

        {items.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.emptyIcon}>🌱</Text>
            <Text style={styles.emptyText}>아직 기록이 없어요.</Text>
            <Text style={styles.emptyHint}>감정을 기록하면 여기 쌓여요.</Text>
          </Card>
        ) : (
          <View style={styles.timelineContainer}>
            {/* 세로선 */}
            <View style={styles.line} />

            {[...items].reverse().map((item) => {
              const meta = TYPE_META[item.type] || { emoji: '📝', label: item.type };
              return (
                <View key={item._id} style={styles.timelineItem}>
                  <View style={styles.dot}>
                    <Text style={styles.dotEmoji}>{meta.emoji}</Text>
                  </View>
                  <Card style={styles.itemCard}>
                    <Text style={styles.itemLabel}>{meta.label}</Text>
                    <Text style={styles.itemDate}>{formatDate(item.created_at)}</Text>
                  </Card>
                </View>
              );
            })}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 20, paddingVertical: 32 },
  title: { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 6 },
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 28 },
  emptyCard: { alignItems: 'center', paddingVertical: 32 },
  emptyIcon: { fontSize: 36, marginBottom: 10 },
  emptyText: { fontSize: 15, color: COLORS.textSecondary },
  emptyHint: { fontSize: 13, color: COLORS.textLight, marginTop: 4 },
  timelineContainer: { position: 'relative', paddingLeft: 8 },
  line: {
    position: 'absolute', left: 22, top: 16, bottom: 16,
    width: 2, backgroundColor: COLORS.secondary,
  },
  timelineItem: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 16 },
  dot: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: '#F0F8F6', borderWidth: 2, borderColor: COLORS.secondary,
    alignItems: 'center', justifyContent: 'center', zIndex: 1,
  },
  dotEmoji: { fontSize: 16 },
  itemCard: { flex: 1, paddingVertical: 12, paddingHorizontal: 14 },
  itemLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  itemDate: { fontSize: 12, color: COLORS.textSecondary, marginTop: 3 },
});
