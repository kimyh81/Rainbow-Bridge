import { Platform } from 'react-native';
import { requireNativeModule } from 'expo-modules-core';

export interface DailyUsage {
  packageName: string;
  appLabel: string;
  usageMinutes: number;
  category: string | null;
}

export interface BehaviorSignal {
  icon: string;
  title: string;
  todayMinutes: number;
  avgMinutes: number;
  changeRate: number;
}

export interface UsageReport {
  daily: DailyUsage[];
  signals: BehaviorSignal[];
  estimatedSleepTime: string | null;
  totalMinutes: number;
  lateNightMinutes: number;
}

const NativeModule = Platform.OS === 'android'
  ? (() => { try { return requireNativeModule('UsageStats'); } catch { return null; } })()
  : null;

export async function hasPermission(): Promise<boolean> {
  if (!NativeModule) return false;
  return NativeModule.hasPermission();
}

export async function openPermissionSettings(): Promise<void> {
  if (!NativeModule) return;
  return NativeModule.openPermissionSettings();
}

export async function collectTodayReport(): Promise<UsageReport | null> {
  if (!NativeModule) return null;
  return NativeModule.collectTodayReport();
}
