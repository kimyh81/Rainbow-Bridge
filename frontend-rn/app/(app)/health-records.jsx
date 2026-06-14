import { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import Card from '@/components/Card';
import Button from '@/components/Button';
import { COLORS } from '@/constants/colors';

const RECORD_TYPES = ['투약', '검진', '수술', '예방접종', '기타'];

export default function HealthRecordsScreen() {
  const [records, setRecords] = useState([]);
  const [form, setForm] = useState({ type: '투약', date: '', description: '' });
  const [showForm, setShowForm] = useState(false);

  function handleAdd() {
    if (!form.description.trim()) return;
    setRecords((prev) => [
      { ...form, id: Date.now().toString() },
      ...prev,
    ]);
    setForm({ type: '투약', date: '', description: '' });
    setShowForm(false);
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>투약·검진 기록</Text>
        <Text style={styles.subtitle}>반려동물의 건강 기록을 남겨두세요.</Text>

        <Button
          onPress={() => setShowForm((v) => !v)}
          variant={showForm ? 'ghost' : 'secondary'}
          style={styles.toggleBtn}
        >
          {showForm ? '취소' : '+ 기록 추가'}
        </Button>

        {showForm ? (
          <Card style={styles.formCard}>
            {/* 유형 */}
            <Text style={styles.label}>유형</Text>
            <View style={styles.typeRow}>
              {RECORD_TYPES.map((t) => (
                <TouchableOpacity
                  key={t}
                  onPress={() => setForm((p) => ({ ...p, type: t }))}
                  style={[styles.typeBtn, form.type === t && styles.typeBtnSelected]}
                >
                  <Text style={[styles.typeText, form.type === t && styles.typeTextSelected]}>
                    {t}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* 날짜 */}
            <Text style={styles.label}>날짜</Text>
            <TextInput
              style={styles.input}
              value={form.date}
              onChangeText={(v) => setForm((p) => ({ ...p, date: v }))}
              placeholder="2026-06-08"
              placeholderTextColor={COLORS.textLight}
            />

            {/* 내용 */}
            <Text style={styles.label}>내용</Text>
            <TextInput
              style={[styles.input, styles.textarea]}
              value={form.description}
              onChangeText={(v) => setForm((p) => ({ ...p, description: v }))}
              placeholder="예) 심장사상충 예방약 투여"
              placeholderTextColor={COLORS.textLight}
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />

            <Button onPress={handleAdd} variant="primary">저장</Button>
          </Card>
        ) : null}

        {records.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Text style={styles.emptyText}>📋 아직 기록이 없어요.</Text>
            <Text style={styles.emptyHint}>위 버튼으로 기록을 추가해보세요.</Text>
          </Card>
        ) : (
          <View style={styles.recordList}>
            {records.map((r) => (
              <Card key={r.id} style={styles.recordCard}>
                <View style={styles.recordHeader}>
                  <View style={styles.typeBadge}>
                    <Text style={styles.typeBadgeText}>{r.type}</Text>
                  </View>
                  {r.date ? <Text style={styles.recordDate}>{r.date}</Text> : null}
                </View>
                <Text style={styles.recordDesc}>{r.description}</Text>
              </Card>
            ))}
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
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 24 },
  toggleBtn: { marginBottom: 16 },
  formCard: { marginBottom: 20 },
  label: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 8, marginTop: 12 },
  typeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  typeBtn: {
    paddingHorizontal: 12, paddingVertical: 7,
    borderRadius: 8, borderWidth: 1.5, borderColor: COLORS.divider,
    backgroundColor: COLORS.white,
  },
  typeBtnSelected: { borderColor: COLORS.selectedBorder, backgroundColor: '#FBF1F3' },
  typeText: { fontSize: 13, color: COLORS.textSecondary },
  typeTextSelected: { color: COLORS.selectedText, fontWeight: '700' },
  input: {
    backgroundColor: COLORS.inputBg, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 14, color: COLORS.textPrimary,
    borderWidth: 1.5, borderColor: COLORS.divider, marginBottom: 4,
  },
  textarea: { minHeight: 80 },
  emptyCard: { alignItems: 'center', paddingVertical: 32 },
  emptyText: { fontSize: 15, color: COLORS.textSecondary },
  emptyHint: { fontSize: 13, color: COLORS.textLight, marginTop: 6 },
  recordList: { gap: 12 },
  recordCard: {},
  recordHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  typeBadge: {
    backgroundColor: '#EBF7F4', borderRadius: 6,
    paddingHorizontal: 10, paddingVertical: 3,
  },
  typeBadgeText: { fontSize: 12, color: '#2E7D6B', fontWeight: '600' },
  recordDate: { fontSize: 12, color: COLORS.textSecondary },
  recordDesc: { fontSize: 14, color: COLORS.textPrimary, lineHeight: 20 },
});
