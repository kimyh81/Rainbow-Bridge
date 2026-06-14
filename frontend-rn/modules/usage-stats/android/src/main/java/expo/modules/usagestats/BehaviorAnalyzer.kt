package expo.modules.usagestats

object BehaviorAnalyzer {

    val CATEGORY_MAP = mapOf(
        "com.discord" to "SOCIAL",
        "com.kakao.talk" to "SOCIAL",
        "com.instagram.android" to "SOCIAL",
        "com.twitter.android" to "SOCIAL",
        "com.facebook.katana" to "SOCIAL",
        "com.google.android.youtube" to "ENTERTAINMENT",
        "com.netflix.mediaclient" to "ENTERTAINMENT",
        "com.zhiliaoapp.musically" to "ENTERTAINMENT",
        "com.google.android.apps.youtube.music" to "ENTERTAINMENT",
        "net.hrdkorea.mobile" to "EDUCATION",
        "com.duolingo" to "EDUCATION",
        "viva.republica.toss" to "FINANCE",
        "com.samsung.android.spay" to "FINANCE"
    )

    fun categoryOf(packageName: String): String? = CATEGORY_MAP[packageName]

    fun analyzeToday(
        todayByPackage: Map<String, Int>,
        lateNightMinutes: Int
    ): List<Map<String, Any>> {
        val signals = mutableListOf<Map<String, Any>>()

        if (lateNightMinutes > 60) {
            signals.add(mapOf(
                "icon" to "⚠️",
                "title" to "새벽 활동 증가",
                "todayMinutes" to lateNightMinutes,
                "avgMinutes" to 30,
                "changeRate" to ((lateNightMinutes - 30) * 100 / 30)
            ))
        }

        val byCat = mutableMapOf<String, Int>()
        todayByPackage.forEach { (pkg, min) ->
            CATEGORY_MAP[pkg]?.let { cat -> byCat[cat] = (byCat[cat] ?: 0) + min }
        }

        byCat["ENTERTAINMENT"]?.let { min ->
            if (min > 120) signals.add(mapOf(
                "icon" to "📺",
                "title" to "영상·미디어 사용 많음",
                "todayMinutes" to min,
                "avgMinutes" to 60,
                "changeRate" to ((min - 60) * 100 / 60)
            ))
        }

        byCat["SOCIAL"]?.let { min ->
            if (min > 120) signals.add(mapOf(
                "icon" to "💬",
                "title" to "소셜 미디어 사용 많음",
                "todayMinutes" to min,
                "avgMinutes" to 60,
                "changeRate" to ((min - 60) * 100 / 60)
            ))
        }

        return signals
    }
}
