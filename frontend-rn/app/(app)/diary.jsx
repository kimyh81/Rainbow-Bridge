import { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, Modal, Pressable,
  StyleSheet, ScrollView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import { gwa } from '@/utils/josa';

const STORAGE_KEY = 'diary_entries';
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

// ─── 날짜 유틸 ───────────────────────────────
function formatLabel(date) {
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'short',
  });
}

function formatYM(date) {
  return date.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long' });
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
}

function getDaysGrid(year, month) {
  const first = new Date(year, month, 1).getDay();
  const last = new Date(year, month + 1, 0).getDate();
  const grid = [];
  for (let i = 0; i < first; i++) grid.push(null);
  for (let d = 1; d <= last; d++) grid.push(d);
  return grid;
}

// ─── 날짜 선택 모달 ──────────────────────────
function DatePickerModal({ visible, selected, onSelect, onClose }) {
  const [view, setView] = useState(new Date(selected));
  const year = view.getFullYear();
  const month = view.getMonth();
  const today = new Date();
  const grid = getDaysGrid(year, month);

  function prevMonth() {
    setView(new Date(year, month - 1, 1));
  }
  function nextMonth() {
    const next = new Date(year, month + 1, 1);
    if (next > today) return;
    setView(next);
  }
  function pickDay(day) {
    if (!day) return;
    const picked = new Date(year, month, day);
    if (picked > today) return;
    onSelect(picked);
    onClose();
  }

  return (
    <Modal visible={visible} transparent animationType="fade">
      <Pressable style={styles.overlay} onPress={onClose}>
        <Pressable style={styles.pickerBox} onPress={() => {}}>
          {/* 헤더 */}
          <View style={styles.pickerHeader}>
            <TouchableOpacity onPress={prevMonth} style={styles.arrowBtn}>
              <Text style={styles.arrowText}>‹</Text>
            </TouchableOpacity>
            <Text style={styles.pickerYM}>{formatYM(view)}</Text>
            <TouchableOpacity
              onPress={nextMonth}
              style={styles.arrowBtn}
              disabled={month === today.getMonth() && year === today.getFullYear()}
            >
              <Text style={[
                styles.arrowText,
                month === today.getMonth() && year === today.getFullYear() && { color: '#D0C8E0' },
              ]}>›</Text>
            </TouchableOpacity>
          </View>

          {/* 요일 */}
          <View style={styles.weekRow}>
            {WEEKDAYS.map((w, i) => (
              <Text key={w} style={[styles.weekday, i === 0 && { color: '#E57373' }, i === 6 && { color: '#7B96CC' }]}>
                {w}
              </Text>
            ))}
          </View>

          {/* 날짜 그리드 */}
          <View style={styles.grid}>
            {grid.map((day, idx) => {
              if (!day) return <View key={`e-${idx}`} style={styles.dayCell} />;
              const cellDate = new Date(year, month, day);
              const isSel = sameDay(cellDate, selected);
              const isTodayCell = sameDay(cellDate, today);
              const isFuture = cellDate > today;
              const col = idx % 7;
              return (
                <TouchableOpacity
                  key={`d-${day}`}
                  style={[styles.dayCell, isSel && styles.dayCellSel]}
                  onPress={() => pickDay(day)}
                  disabled={isFuture}
                >
                  <Text style={[
                    styles.dayText,
                    col === 0 && { color: '#E57373' },
                    col === 6 && { color: '#7B96CC' },
                    isFuture && { color: '#D0C8E0' },
                    isTodayCell && !isSel && styles.dayToday,
                    isSel && styles.dayTextSel,
                  ]}>
                    {day}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
            <Text style={styles.closeBtnText}>닫기</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

// ─── 메인 화면 ────────────────────────────────
export default function DiaryScreen() {
  const router = useRouter();
  const [entries, setEntries] = useState([]);
  const [writing, setWriting] = useState(false);
  const [content, setContent] = useState('');
  const [petName, setPetName] = useState('소중한 친구');
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [showPicker, setShowPicker] = useState(false);
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    AsyncStorage.getItem('pet_name').then(v => v && setPetName(v));
    AsyncStorage.getItem(STORAGE_KEY).then(stored => {
      if (stored) setEntries(JSON.parse(stored));
    });
  }, []);

  function openNew() {
    setEditingId(null);
    setContent('');
    setSelectedDate(new Date());
    setWriting(true);
  }

  function openEdit(entry) {
    setEditingId(entry.id);
    setContent(entry.content);
    setSelectedDate(new Date(entry.dateRaw));
    setWriting(true);
  }

  function cancelWrite() {
    setWriting(false);
    setContent('');
    setEditingId(null);
  }

  async function saveEntry() {
    if (!content.trim()) return;
    let updated;
    if (editingId) {
      updated = entries.map(e =>
        e.id === editingId
          ? { ...e, content: content.trim(), dateLabel: formatLabel(selectedDate), dateRaw: selectedDate.toISOString() }
          : e
      );
    } else {
      const entry = {
        id: Date.now().toString(),
        dateLabel: formatLabel(selectedDate),
        dateRaw: selectedDate.toISOString(),
        content: content.trim(),
      };
      updated = [entry, ...entries];
    }
    setEntries(updated);
    setContent('');
    setWriting(false);
    setEditingId(null);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }

  async function deleteEntry(id) {
    const updated = entries.filter(e => e.id !== id);
    setEntries(updated);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }

  return (
    <LinearGradient
      colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']}
      locations={[0, 0.35, 0.6, 1]}
      style={styles.gradient}
    >
      <SafeAreaView style={styles.safe}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.logo}>🌈 레인보우 브릿지</Text>
          <Text style={styles.subtitle}>소중한 가족을 기억해요</Text>

          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backText}>← 이전</Text>
          </TouchableOpacity>

          <Text style={styles.title}>📔 {petName}{gwa(petName)}의 일기</Text>
          <Text style={styles.desc}>함께한 하루하루를 기록해요.</Text>

          {/* 글쓰기 박스 */}
          {writing ? (
            <View style={styles.writeBox}>
              {/* 날짜 선택 버튼 */}
              <TouchableOpacity onPress={() => setShowPicker(true)} style={styles.datePicker}>
                <Text style={styles.datePickerLabel}>{formatLabel(selectedDate)}</Text>
                <Text style={styles.datePickerIcon}>📅</Text>
              </TouchableOpacity>

              <TextInput
                style={styles.writeInput}
                value={content}
                onChangeText={setContent}
                placeholder={`${petName}${gwa(petName)} 있었던 일을 적어주세요.`}
                placeholderTextColor="#A89FBC"
                multiline
                numberOfLines={5}
                textAlignVertical="top"
                autoFocus
              />
              <View style={styles.writeActions}>
                <TouchableOpacity style={styles.cancelBtn} onPress={cancelWrite}>
                  <Text style={styles.cancelText}>취소</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={saveEntry} activeOpacity={0.8} style={styles.saveBtnWrap}>
                  <LinearGradient
                    colors={['#E8DFF5', '#FCE1E4']}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                    style={styles.saveBtn}
                  >
                    <Text style={styles.saveBtnText}>{editingId ? '수정 완료' : '저장하기'}</Text>
                  </LinearGradient>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <TouchableOpacity style={styles.newEntryBtn} onPress={openNew} activeOpacity={0.8}>
              <LinearGradient
                colors={['#E8DFF5', '#FCE1E4']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                style={styles.newEntryGrad}
              >
                <Text style={styles.newEntryText}>✏️ 일기 쓰기</Text>
              </LinearGradient>
            </TouchableOpacity>
          )}

          {/* 일기 목록 */}
          {entries.length > 0 && (
            <View style={styles.entriesList}>
              {entries.map(entry => (
                <View key={entry.id} style={styles.entryCard}>
                  <View style={styles.entryTop}>
                    <Text style={styles.entryDate}>{entry.dateLabel}</Text>
                    <View style={styles.entryActions}>
                      <TouchableOpacity onPress={() => openEdit(entry)} style={styles.actionBtn}>
                        <Text style={styles.editText}>수정</Text>
                      </TouchableOpacity>
                      <TouchableOpacity onPress={() => deleteEntry(entry.id)} style={styles.actionBtn}>
                        <Text style={styles.deleteText}>삭제</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                  <Text style={styles.entryContent}>{entry.content}</Text>
                </View>
              ))}
            </View>
          )}

          {entries.length === 0 && !writing && (
            <Text style={styles.emptyText}>아직 기록된 일기가 없어요.{'\n'}오늘의 이야기를 들려주세요. 🌸</Text>
          )}
        </ScrollView>
      </SafeAreaView>

      <DatePickerModal
        visible={showPicker}
        selected={selectedDate}
        onSelect={setSelectedDate}
        onClose={() => setShowPicker(false)}
      />
    </LinearGradient>
  );
}

// ─── 스타일 ───────────────────────────────────
const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 20, paddingVertical: 32, paddingBottom: 48 },

  logo: { fontSize: 22, fontWeight: '700', color: '#5B4E75', textAlign: 'center', marginBottom: 4 },
  subtitle: { fontSize: 13, color: '#8A7D9E', textAlign: 'center', marginBottom: 20 },
  backBtn: { marginBottom: 16 },
  backText: { fontSize: 14, color: '#8A7D9E' },
  title: { fontSize: 17, fontWeight: '800', color: '#5B4E75', marginBottom: 6 },
  desc: { fontSize: 13, color: '#8A7D9E', marginBottom: 20 },

  // 글쓰기 박스
  writeBox: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16, borderWidth: 1.5, borderColor: '#E5DCF0',
    padding: 16, marginBottom: 20,
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07, shadowRadius: 6, elevation: 1,
  },
  datePicker: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#F5F0FA', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10,
    marginBottom: 12,
  },
  datePickerLabel: { fontSize: 13, color: '#5B4E75', fontWeight: '600' },
  datePickerIcon: { fontSize: 16 },

  writeInput: {
    fontSize: 14, color: '#4A4A4A', lineHeight: 22,
    minHeight: 110, paddingTop: 0, textAlignVertical: 'top', marginBottom: 12,
  },
  writeActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10 },
  cancelBtn: {
    paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12,
    borderWidth: 1.5, borderColor: '#E5DCF0',
  },
  cancelText: { fontSize: 14, color: '#8A7D9E', fontWeight: '600' },
  saveBtnWrap: {
    shadowColor: '#DAEAF6', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4, shadowRadius: 8, elevation: 3,
  },
  saveBtn: { height: 40, paddingHorizontal: 20, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  saveBtnText: { color: '#5B4E75', fontSize: 14, fontWeight: '700' },

  newEntryBtn: {
    shadowColor: '#DAEAF6', shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4, shadowRadius: 10, elevation: 3, marginBottom: 24,
  },
  newEntryGrad: { height: 52, borderRadius: 16, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#D4C5F0' },
  newEntryText: { color: '#5B4E75', fontSize: 15, fontWeight: '700' },

  // 일기 목록
  entriesList: { gap: 12 },
  entryCard: {
    backgroundColor: '#FFFFFF', borderRadius: 16, borderWidth: 1.5, borderColor: '#E5DCF0',
    paddingHorizontal: 16, paddingVertical: 14,
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06, shadowRadius: 5, elevation: 1,
  },
  entryTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  entryDate: { fontSize: 12, color: '#A89FBC', fontWeight: '600' },
  entryActions: { flexDirection: 'row', gap: 10 },
  actionBtn: { paddingHorizontal: 4, paddingVertical: 2 },
  editText: { fontSize: 13, color: '#8A7D9E', fontWeight: '600' },
  deleteText: { fontSize: 13, color: '#E57373', fontWeight: '600' },
  entryContent: { fontSize: 14, color: '#4A4A4A', lineHeight: 21 },

  emptyText: {
    textAlign: 'center', color: '#A89FBC', fontSize: 14, lineHeight: 22, marginTop: 32,
  },

  // 날짜 피커 모달
  overlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'center', alignItems: 'center',
  },
  pickerBox: {
    backgroundColor: '#FFFFFF', borderRadius: 20, padding: 20,
    width: 320,
    shadowColor: '#5B4E75', shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18, shadowRadius: 20, elevation: 10,
  },
  pickerHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14,
  },
  arrowBtn: { padding: 8 },
  arrowText: { fontSize: 24, color: '#5B4E75', fontWeight: '700' },
  pickerYM: { fontSize: 16, fontWeight: '800', color: '#5B4E75' },

  weekRow: { flexDirection: 'row', marginBottom: 6 },
  weekday: {
    flex: 1, textAlign: 'center', fontSize: 12, fontWeight: '700', color: '#8A7D9E', paddingVertical: 4,
  },

  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  dayCell: {
    width: `${100 / 7}%`, aspectRatio: 1,
    justifyContent: 'center', alignItems: 'center',
  },
  dayCellSel: {
    backgroundColor: '#C4A8D8', borderRadius: 50,
  },
  dayText: { fontSize: 14, color: '#4A4A4A', fontWeight: '500' },
  dayToday: { color: '#5B4E75', fontWeight: '800' },
  dayTextSel: { color: '#FFFFFF', fontWeight: '800' },

  closeBtn: {
    marginTop: 14, paddingVertical: 12, borderRadius: 12,
    backgroundColor: '#F5F0FA', alignItems: 'center',
  },
  closeBtnText: { fontSize: 14, color: '#5B4E75', fontWeight: '700' },
});
