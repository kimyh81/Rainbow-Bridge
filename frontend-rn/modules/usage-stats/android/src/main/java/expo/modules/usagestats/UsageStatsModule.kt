package expo.modules.usagestats

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Process
import android.provider.Settings
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.text.SimpleDateFormat
import java.util.*

class UsageStatsModule : Module() {
    override fun definition() = ModuleDefinition {
        Name("UsageStats")

        AsyncFunction("hasPermission") {
            val context = appContext.reactContext ?: return@AsyncFunction false
            val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
            val mode = appOps.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.packageName
            )
            mode == AppOpsManager.MODE_ALLOWED
        }

        AsyncFunction("openPermissionSettings") {
            val context = appContext.reactContext ?: return@AsyncFunction
            context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            })
        }

        AsyncFunction("collectTodayReport") {
            val context = appContext.reactContext ?: return@AsyncFunction null
            collectReport(context)
        }
    }

    private fun collectReport(context: Context): Map<String, Any?> {
        val cal = Calendar.getInstance()
        val endTime = cal.timeInMillis
        cal.set(Calendar.HOUR_OF_DAY, 0); cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0); cal.set(Calendar.MILLISECOND, 0)
        val startTime = cal.timeInMillis

        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

        // 앱 레이블 캐시
        val labelCache = try {
            context.packageManager
                .getInstalledApplications(PackageManager.GET_META_DATA)
                .associate { it.packageName to context.packageManager.getApplicationLabel(it).toString() }
        } catch (e: Exception) {
            emptyMap()
        }

        // 일별 사용 시간 수집 (1분 이상)
        val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, startTime, endTime)
        val daily = stats
            .filter { it.totalTimeInForeground > 60_000L && it.packageName != context.packageName }
            .map { stat ->
                mapOf(
                    "packageName" to stat.packageName,
                    "appLabel" to (labelCache[stat.packageName] ?: stat.packageName),
                    "usageMinutes" to (stat.totalTimeInForeground / 60_000).toInt(),
                    "category" to BehaviorAnalyzer.categoryOf(stat.packageName)
                )
            }
            .sortedByDescending { it["usageMinutes"] as Int }

        // 22시 이후 새벽 사용 시간 + 마지막 활동 시각
        val nightStart = Calendar.getInstance().apply {
            timeInMillis = startTime
            set(Calendar.HOUR_OF_DAY, 22); set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
        }.timeInMillis

        var lateNightMs = 0L
        var lastActiveMs = 0L
        val fgStart = mutableMapOf<String, Long>()
        val events = usm.queryEvents(startTime, endTime)
        val ev = UsageEvents.Event()

        while (events.hasNextEvent()) {
            events.getNextEvent(ev)
            val pkg = ev.packageName ?: continue
            if (pkg == context.packageName) continue

            if (ev.timeStamp >= nightStart) lastActiveMs = maxOf(lastActiveMs, ev.timeStamp)

            when (ev.eventType) {
                UsageEvents.Event.MOVE_TO_FOREGROUND -> fgStart[pkg] = ev.timeStamp
                UsageEvents.Event.MOVE_TO_BACKGROUND -> {
                    val start = fgStart.remove(pkg) ?: continue
                    val overlapStart = maxOf(start, nightStart)
                    if (ev.timeStamp > nightStart) {
                        lateNightMs += ev.timeStamp - overlapStart
                    }
                }
            }
        }

        val totalMinutes = daily.sumOf { it["usageMinutes"] as Int }
        val lateNightMinutes = (lateNightMs / 60_000).toInt()
        val todayByPackage = daily.associate { it["packageName"] as String to it["usageMinutes"] as Int }
        val signals = BehaviorAnalyzer.analyzeToday(todayByPackage, lateNightMinutes)

        val sleepTime = if (lastActiveMs > 0) {
            val fmt = SimpleDateFormat("HH:mm", Locale.getDefault())
            "${fmt.format(Date(lastActiveMs))} 이후 취침 추정"
        } else null

        return mapOf(
            "daily" to daily,
            "signals" to signals,
            "estimatedSleepTime" to sleepTime,
            "totalMinutes" to totalMinutes,
            "lateNightMinutes" to lateNightMinutes
        )
    }
}
