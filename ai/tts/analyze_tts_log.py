"""TTS 서버 로그 분석기 — start_tts.bat(server.py) 로그를 읽어 평가.

실행 중인 TTS 서버는 **건드리지 않습니다.** 워치 모드도 GET /health 만 호출
(모델 로드·GPU 합성 없음). server.py 의 동기/비동기 합성 경로는 일절 안 부릅니다.

두 가지 용도:

1) 파일 분석 (오프라인) — start_tts.bat 콘솔 출력을 파일로 받아 분석:
       # 콘솔 로그를 파일로 남기려면(실행 중인 서버 안 건드리고, 다음 기동부터):
       #   conda run --no-capture-output -n qwen3-tts python ai/tts/server.py > tts.log 2>&1
       python ai/tts/analyze_tts_log.py tts.log

   uvicorn 액세스 로그( "POST /synthesize HTTP/1.1" 200 )와 lifespan/degraded
   print 를 파싱해 엔드포인트별 요청수·HTTP 상태분포·에러·503(폴백 발생) 신호를
   집계합니다. 줄 앞에 타임스탬프가 있으면 시간범위·분당 요청도.

   **응답 엔진 호출 요약**도 냅니다: 200=Qwen3(로컬·무료) / 503·500=Google(폴백·
   유료)으로 엔진별 사용량을 나누고, Google 단가($16/100만자)·평균 글자수 가정으로
   1콜 평균 비용을 추정합니다(--avg-chars/--price-per-million/--usd-krw 로 조정).

2) 라이브 워치 (온라인, 읽기전용) — 실행 중 서버의 /health 를 주기 폴링해
   **타임스탬프 + 응답시간(ms)** 타임라인을 기록:
       python ai/tts/analyze_tts_log.py --watch
       python ai/tts/analyze_tts_log.py --watch --url http://127.0.0.1:8002 --interval 5 --out health.csv

   model_ready / degraded(GPU 정체→폴백) 변화와 health 응답지연을 시계열로 남기고,
   Ctrl-C 로 멈추면 요약(가동 표본 수, degraded 비율, 평균/최대 지연)을 출력합니다.

stdlib 만 사용 — qwen3-tts conda 환경 밖 아무 파이썬에서도 동작.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

# Windows 콘솔 기본(cp949)은 em-dash·이모지를 못 찍어 UnicodeEncodeError → UTF-8 강제.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

# uvicorn 액세스 로그 한 줄에서 메서드/경로/상태코드 추출.
#   예: INFO:     127.0.0.1:51664 - "POST /synthesize HTTP/1.1" 200 OK
_ACCESS_RE = re.compile(
    r'"(?P<method>GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+'
    r'(?P<path>\S+)\s+HTTP/[\d.]+"\s+(?P<status>\d{3})'
)

# 줄 맨 앞 타임스탬프(있을 때만). uvicorn 기본 로그엔 없지만, 사용자가
# `ts | 로그` 식으로 찍거나 logging 포맷에 시간을 넣었을 때 잡아준다.
#   예: 2026-06-16 11:35:02 / 2026-06-16T11:35:02
_STAMP_RE = re.compile(r"^\s*\[?(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")

# server.py 가 직접 찍는 신호성 print.
_LIFESPAN_FAIL = "[lifespan] 모델 사전로드 실패"

# 합성 결과 헤더( X-Audio-Duration )가 로그에 섞여 들어온 경우 합성 길이 수집용.
_DURATION_RE = re.compile(r"X-Audio-Duration[\"']?\s*[:=]\s*[\"']?(?P<dur>[\d.]+)")

# 경로 정규화 — job_id 가 붙는 경로는 묶어서 센다.
#   /synthesize/status/ab12.. -> /synthesize/status/{id}
_JOB_PATH_RE = re.compile(r"^(/(?:tts/)?synthesize/(?:status|result))/[0-9a-f]+", re.I)

# 합성 제출 엔드포인트(동기·비동기) — 여기서 503 이면 Qwen3 거부 → 백엔드 Google 폴백.
_SUBMIT_PATHS = {
    "/synthesize",
    "/tts/synthesize",
    "/synthesize/async",
    "/tts/synthesize/async",
}
# 비동기 결과 다운로드 — 200=Qwen3 완료, 500=합성 에러(→백엔드 폴백).
_RESULT_PATHS = {"/synthesize/result/{id}", "/tts/synthesize/result/{id}"}
# 동기 합성 성공 = 여기 200.
_SYNC_PATHS = {"/synthesize", "/tts/synthesize"}

# 응답 엔진 — TTS 서버(이 server.py)는 Qwen3 로컬, 503/실패면 백엔드가 Google 폴백.
ENGINE_QWEN3 = "Qwen3 (로컬·무료)"
ENGINE_GOOGLE = "Google (폴백·유료)"

# Google Cloud TTS Neural2 단가(USD/100만자) — ko-KR-Neural2-* (tts.py 확인).
_DEFAULT_PRICE_PER_M = 16.0
# 평균 글자수/콜 — server.py 주석 "memorial 강제 600자" 기준 기본값(로그엔 글자수 없음).
_DEFAULT_AVG_CHARS = 600
_DEFAULT_USD_KRW = 1450.0


def _normalize_path(path: str) -> str:
    """쿼리스트링 제거 + job_id 경로 묶기."""
    path = path.split("?", 1)[0]
    m = _JOB_PATH_RE.match(path)
    if m:
        return m.group(1) + "/{id}"
    return path


def _status_class(status: int) -> str:
    return f"{status // 100}xx"


def analyze_file(
    path: str,
    *,
    avg_chars: int = _DEFAULT_AVG_CHARS,
    price_per_million: float = _DEFAULT_PRICE_PER_M,
    usd_krw: float = _DEFAULT_USD_KRW,
    csv_out: str | None = None,
    md_out: str | None = None,
) -> int:
    """로그 파일을 파싱해 리포트를 출력. 종료코드 반환(0=정상)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"로그 파일을 열 수 없음: {e}", file=sys.stderr)
        return 2

    endpoint_counts: Counter[str] = Counter()
    status_counts: Counter[int] = Counter()
    class_counts: Counter[str] = Counter()
    # 엔드포인트 × 상태코드 교차표 (에러가 어디서 나는지)
    endpoint_status: dict[str, Counter[int]] = defaultdict(Counter)
    errors: list[str] = []  # 4xx/5xx 원문 줄(앞부분)
    lifespan_fails = 0
    durations: list[float] = []
    timestamps: list[datetime] = []
    total_requests = 0
    # 응답 엔진 집계
    engine_counts: Counter[str] = Counter()  # Qwen3 / Google
    synth_fail = 0  # 합성 요청인데 4xx(503·500 제외) 실패

    for raw in lines:
        line = raw.rstrip("\n")

        if _LIFESPAN_FAIL in line:
            lifespan_fails += 1

        dm = _DURATION_RE.search(line)
        if dm:
            try:
                durations.append(float(dm.group("dur")))
            except ValueError:
                pass

        m = _ACCESS_RE.search(line)
        if not m:
            continue

        total_requests += 1
        path_n = _normalize_path(m.group("path"))
        status = int(m.group("status"))
        endpoint_counts[path_n] += 1
        status_counts[status] += 1
        class_counts[_status_class(status)] += 1
        endpoint_status[path_n][status] += 1
        if status >= 400:
            errors.append(line.strip()[:200])

        # 응답 엔진 귀속(합성 관련 경로만):
        #   동기 /synthesize 200      → Qwen3 성공
        #   결과 /synthesize/result 200 → Qwen3 완료(비동기)
        #   제출 503                  → Qwen3 거부 → 백엔드 Google 폴백
        #   결과 500                  → 합성 에러(degraded) → Google 폴백
        #   그 외 4xx(제출 400 등)     → 합성 실패(엔진 미귀속)
        if status == 200 and (path_n in _SYNC_PATHS or path_n in _RESULT_PATHS):
            engine_counts[ENGINE_QWEN3] += 1
        elif status == 503 and path_n in _SUBMIT_PATHS:
            engine_counts[ENGINE_GOOGLE] += 1
        elif status == 500 and path_n in _RESULT_PATHS:
            engine_counts[ENGINE_GOOGLE] += 1
        elif status >= 400 and (path_n in _SUBMIT_PATHS or path_n in _RESULT_PATHS):
            synth_fail += 1

        sm = _STAMP_RE.match(line)
        if sm:
            ts = sm.group("ts").replace("T", " ")
            try:
                timestamps.append(datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                pass

    engine = _build_engine_summary(
        engine_counts,
        synth_fail,
        avg_chars=avg_chars,
        price_per_million=price_per_million,
        usd_krw=usd_krw,
    )
    _print_report(
        path=path,
        total_requests=total_requests,
        endpoint_counts=endpoint_counts,
        status_counts=status_counts,
        class_counts=class_counts,
        endpoint_status=endpoint_status,
        errors=errors,
        lifespan_fails=lifespan_fails,
        durations=durations,
        timestamps=timestamps,
        engine=engine,
    )

    # 제출용 파일 내보내기
    if csv_out or md_out:
        if timestamps:
            period = f"{min(timestamps)} ~ {max(timestamps)}"
        else:
            period = "타임스탬프 없는 로그(기간 미상)"
        if csv_out:
            write_engine_csv(engine, csv_out)
            print(f"\n[저장] CSV → {csv_out}")
        if md_out:
            write_engine_md(engine, md_out, source=path, period=period)
            print(f"[저장] Markdown → {md_out}")
    return 0


def _print_report(
    *,
    path: str,
    total_requests: int,
    endpoint_counts: Counter,
    status_counts: Counter,
    class_counts: Counter,
    endpoint_status: dict,
    errors: list,
    lifespan_fails: int,
    durations: list,
    timestamps: list,
    engine: dict,
) -> None:
    bar = "=" * 60
    print(bar)
    print(f"TTS 로그 분석 리포트 — {path}")
    print(bar)

    if total_requests == 0:
        print("\n해석할 uvicorn 액세스 로그 줄이 없음.")
        print("server.py 출력을 그대로 받았는지 확인하세요(>> tts.log 2>&1).")
        if lifespan_fails:
            print(
                f"\n⚠️ [lifespan] 모델 사전로드 실패 {lifespan_fails}건 발견 "
                "→ lazy 로드 폴백(첫 합성 콜드스타트)."
            )
        return

    # 시간 범위
    if timestamps:
        t0, t1 = min(timestamps), max(timestamps)
        span = (t1 - t0).total_seconds()
        print(f"\n[시간 범위] {t0} ~ {t1}  ({span/60:.1f}분)")
        if span > 0:
            print(f"           평균 요청률 {total_requests / (span/60):.1f} req/분")
    else:
        print("\n[시간 범위] 타임스탬프 없는 로그(uvicorn 기본) — 시간 분석 생략")
        print("           시간을 보려면 --watch 모드 또는 시간 찍힌 로깅을 쓰세요.")

    print(f"\n[총 요청] {total_requests}건")

    print("\n[HTTP 상태 분포]")
    for cls in sorted(class_counts):
        mark = " ⚠️" if cls in ("4xx", "5xx") else ""
        print(f"  {cls}: {class_counts[cls]}{mark}")
    for status in sorted(status_counts):
        print(f"    └ {status}: {status_counts[status]}")

    print("\n[엔드포인트별 요청]")
    for ep, cnt in endpoint_counts.most_common():
        codes = endpoint_status[ep]
        err = sum(c for s, c in codes.items() if s >= 400)
        tail = f"  (에러 {err})" if err else ""
        print(f"  {cnt:>5}  {ep}{tail}")

    # 503 = 혼잡/degraded → 백엔드 gTTS 폴백 발생 신호(메모리: degraded 죽음의 소용돌이)
    n_503 = status_counts.get(503, 0)
    if n_503:
        print(
            f"\n⚠️ 503(서버 혼잡/GPU 정체→폴백) {n_503}건 "
            "— degraded 전환 또는 동시요청 과부하 의심."
        )
    if lifespan_fails:
        print(
            f"⚠️ [lifespan] 모델 사전로드 실패 {lifespan_fails}건 "
            "→ 첫 합성 콜드스타트 지연."
        )

    # ── 응답 엔진 호출 로그 요약 (사용량 · 1콜 평균 비용 · 엔진 종류) ──────────
    print("\n[응답 엔진 호출 요약]")
    if engine["total"] == 0 and engine["fail"] == 0:
        print("  합성 호출 기록 없음(/synthesize 류 200/503 미발견).")
    else:
        print(
            f"  합성 호출 합계: {engine['total']}건  "
            f"(실패 4xx {engine['fail']}건 별도)"
        )
        print(
            f"    {ENGINE_QWEN3:<18} {engine['qwen3']:>5}건 "
            f"({engine['qwen3_pct']:4.0f}%)"
        )
        print(
            f"    {ENGINE_GOOGLE:<18} {engine['google']:>5}건 "
            f"({engine['google_pct']:4.0f}%)"
        )

        print(
            f"\n  [추정 비용]  (Google Neural2 ${engine['price_per_million']:.0f}/100만자, "
            f"평균 {engine['avg_chars']}자/콜 가정 — --avg-chars/--price-per-million 조정)"
        )
        print(
            f"    Google 폴백 {engine['google']}건 × {engine['avg_chars']}자 "
            f"= {engine['fallback_chars']:,}자"
        )
        print(
            f"    총 추정 ≈ ${engine['cost_usd']:.4f}  (≈ {engine['cost_krw']:,.1f}원)"
        )
        print(
            f"    1콜 평균 ≈ {engine['per_call_krw']:,.2f}원  "
            f"(Qwen3 무료 포함 {engine['total']}콜 분산)"
        )
        if engine["google"]:
            print(f"    └ 폴백 1콜당 ≈ {engine['per_fallback_krw']:,.2f}원")

    if durations:
        ds = sorted(durations)
        print("\n[합성 오디오 길이(X-Audio-Duration, 초)]")
        print(
            f"  건수 {len(ds)} / 최소 {ds[0]:.1f} / 중앙 {ds[len(ds)//2]:.1f} "
            f"/ 최대 {ds[-1]:.1f}"
        )

    if errors:
        print(f"\n[에러 줄 최근 {min(10, len(errors))}건]")
        for e in errors[-10:]:
            print(f"  {e}")
    print()


# ── 응답 엔진 요약: 구조화 + 제출용 파일 내보내기 ─────────────────────────────


def _build_engine_summary(
    engine_counts: Counter,
    synth_fail: int,
    *,
    avg_chars: int,
    price_per_million: float,
    usd_krw: float,
) -> dict:
    """엔진별 사용량·추정비용을 구조화한 dict — 출력/CSV/MD 공용."""
    qwen3 = engine_counts.get(ENGINE_QWEN3, 0)
    google = engine_counts.get(ENGINE_GOOGLE, 0)
    total = qwen3 + google
    fallback_chars = google * avg_chars
    cost_usd = fallback_chars / 1_000_000 * price_per_million
    cost_krw = cost_usd * usd_krw
    return {
        "qwen3": qwen3,
        "google": google,
        "total": total,
        "fail": synth_fail,
        "qwen3_pct": (qwen3 / total * 100) if total else 0.0,
        "google_pct": (google / total * 100) if total else 0.0,
        "fallback_chars": fallback_chars,
        "cost_usd": cost_usd,
        "cost_krw": cost_krw,
        "per_call_krw": (cost_krw / total) if total else 0.0,
        "per_fallback_krw": (cost_krw / google) if google else 0.0,
        "avg_chars": avg_chars,
        "price_per_million": price_per_million,
        "usd_krw": usd_krw,
    }


def _now_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def write_engine_csv(s: dict, path: str) -> None:
    """엔진 요약을 제출용 CSV 로 저장(엑셀 한글 위해 utf-8-sig).

    표: 엔진 / 호출수 / 비율(%) / 추정비용(원) / 1콜평균(원). 가정값은 하단 메모.
    """
    import csv

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["엔진", "호출수", "비율(%)", "추정비용(원)", "1콜평균(원)"])
        w.writerow([ENGINE_QWEN3, s["qwen3"], f"{s['qwen3_pct']:.1f}", "0.00", "0.00"])
        w.writerow(
            [
                ENGINE_GOOGLE,
                s["google"],
                f"{s['google_pct']:.1f}",
                f"{s['cost_krw']:.2f}",
                f"{s['per_fallback_krw']:.2f}",
            ]
        )
        w.writerow(
            [
                "합계",
                s["total"],
                "100.0",
                f"{s['cost_krw']:.2f}",
                f"{s['per_call_krw']:.2f}",
            ]
        )
        w.writerow([])
        w.writerow(["합성 실패(4xx)", s["fail"]])
        w.writerow([])
        w.writerow(["[추정 가정]"])
        w.writerow(["Google 단가(USD/100만자)", s["price_per_million"]])
        w.writerow(["평균 글자수/콜", s["avg_chars"]])
        w.writerow(["환율(USD→KRW)", s["usd_krw"]])
        w.writerow(["생성시각", _now_str()])


def write_engine_md(s: dict, path: str, *, source: str, period: str) -> None:
    """엔진 요약을 제출용 Markdown 리포트로 저장."""
    lines = [
        "# 응답 엔진 호출 로그 요약",
        "",
        f"- 원본 로그: `{source}`",
        f"- 집계 기간: {period}",
        f"- 생성시각: {_now_str()}",
        "",
        "## 엔진별 사용량 · 비용",
        "",
        "| 엔진 | 호출수 | 비율 | 추정비용(원) | 1콜 평균(원) |",
        "|------|-------:|-----:|------------:|------------:|",
        f"| {ENGINE_QWEN3} | {s['qwen3']} | {s['qwen3_pct']:.0f}% | 0.00 | 0.00 |",
        f"| {ENGINE_GOOGLE} | {s['google']} | {s['google_pct']:.0f}% | "
        f"{s['cost_krw']:,.2f} | {s['per_fallback_krw']:,.2f} |",
        f"| **합계** | **{s['total']}** | **100%** | "
        f"**{s['cost_krw']:,.2f}** | **{s['per_call_krw']:,.2f}** |",
        "",
        f"- 합성 실패(4xx): {s['fail']}건",
        f"- 총 추정 비용: ${s['cost_usd']:.4f} (≈ {s['cost_krw']:,.1f}원)",
        "",
        "## 비용 추정 가정",
        "",
        "- 엔진 귀속: HTTP 200 = Qwen3(로컬·무료) / 503·500 = Google 폴백(유료)",
        f"- Google Neural2 단가: ${s['price_per_million']:.0f} / 100만자",
        f"- 평균 글자수/콜: {s['avg_chars']}자 (로그에 글자수 미기록 → 가정값)",
        f"- 환율: 1 USD = {s['usd_krw']:,.0f}원",
        "",
        "> Qwen3 는 로컬 GPU 추론이라 과금 0원. 비용은 Google 폴백 호출에서만 발생합니다.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── 라이브 워치(읽기전용) ─────────────────────────────────────────────────────


def _probe_health(base_url: str, timeout: float):
    """GET /health 한 번 — (latency_ms, payload|None, error|None)."""
    url = base_url.rstrip("/") + "/health"
    req = urllib.request.Request(url, headers={"User-Agent": "tts-log-analyzer"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
        latency_ms = (time.perf_counter() - start) * 1000
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"_raw": body[:120]}
        return latency_ms, payload, None
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return latency_ms, None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — 연결 실패도 한 표본으로 기록
        latency_ms = (time.perf_counter() - start) * 1000
        return latency_ms, None, type(e).__name__


def watch(base_url: str, interval: float, out_csv: str | None) -> int:
    """/health 를 interval 초마다 폴링해 타임라인 기록(읽기전용). Ctrl-C 로 종료."""
    print(f"TTS /health 워치 시작 — {base_url}  (간격 {interval}s, Ctrl-C 종료)")
    print(f"{'시각':<19}  {'지연(ms)':>9}  {'상태':<6}  ready  degraded")
    print("-" * 60)

    csv_f = None
    if out_csv:
        csv_f = open(out_csv, "a", encoding="utf-8")
        if csv_f.tell() == 0:
            csv_f.write("timestamp,latency_ms,ok,model_ready,degraded,error\n")

    samples = 0
    ok_count = 0
    degraded_count = 0
    latencies: list[float] = []
    try:
        while True:
            now = datetime.now(timezone.utc).astimezone()
            ts = now.strftime("%Y-%m-%d %H:%M:%S")
            latency_ms, payload, err = _probe_health(base_url, timeout=interval + 5)
            samples += 1
            latencies.append(latency_ms)

            if payload is not None:
                ok_count += 1
                ready = bool(payload.get("model_ready"))
                degraded = bool(payload.get("degraded"))
                if degraded:
                    degraded_count += 1
                status_txt = "ok"
                print(
                    f"{ts:<19}  {latency_ms:>9.1f}  {status_txt:<6}  "
                    f"{str(ready):<5}  {degraded}"
                )
            else:
                ready = ""
                degraded = ""
                status_txt = err or "ERR"
                print(f"{ts:<19}  {latency_ms:>9.1f}  {status_txt:<6}  -      -")

            if csv_f:
                csv_f.write(
                    f"{ts},{latency_ms:.1f},{payload is not None},"
                    f"{ready},{degraded},{err or ''}\n"
                )
                csv_f.flush()

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n중단됨.")
    finally:
        if csv_f:
            csv_f.close()

    # 요약
    print("=" * 60)
    print("워치 요약")
    print("=" * 60)
    print(f"  표본 {samples}건 / 응답성공 {ok_count} / 실패 {samples - ok_count}")
    if samples:
        print(
            f"  degraded(GPU정체→폴백) 표본 {degraded_count} "
            f"({degraded_count/samples*100:.0f}%)"
        )
    if latencies:
        ls = sorted(latencies)
        print(
            f"  health 지연 ms — 최소 {ls[0]:.1f} / 중앙 {ls[len(ls)//2]:.1f} "
            f"/ 최대 {ls[-1]:.1f}"
        )
    if out_csv:
        print(f"  CSV 저장: {out_csv}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="TTS 서버 로그 분석기 (실행 중 서버는 /health 만 읽음)",
    )
    p.add_argument("logfile", nargs="?", help="분석할 server.py 콘솔 로그 파일")
    p.add_argument(
        "--watch",
        action="store_true",
        help="실행 중 서버 /health 라이브 폴링(읽기전용)",
    )
    p.add_argument(
        "--url",
        default="http://127.0.0.1:8002",
        help="워치 대상 베이스 URL (기본 로컬 8002)",
    )
    p.add_argument(
        "--interval", type=float, default=5.0, help="워치 폴링 간격(초, 기본 5)"
    )
    p.add_argument("--out", help="워치 결과를 append 할 CSV 경로")
    p.add_argument(
        "--avg-chars",
        type=int,
        default=_DEFAULT_AVG_CHARS,
        help=f"비용 추정용 평균 글자수/콜 (기본 {_DEFAULT_AVG_CHARS})",
    )
    p.add_argument(
        "--price-per-million",
        type=float,
        default=_DEFAULT_PRICE_PER_M,
        help=f"Google TTS 단가 USD/100만자 (기본 {_DEFAULT_PRICE_PER_M})",
    )
    p.add_argument(
        "--usd-krw",
        type=float,
        default=_DEFAULT_USD_KRW,
        help=f"환율 USD→KRW (기본 {_DEFAULT_USD_KRW:.0f})",
    )
    p.add_argument("--csv", help="응답 엔진 요약을 제출용 CSV 로 저장(엑셀)")
    p.add_argument("--md", help="응답 엔진 요약을 제출용 Markdown 으로 저장")
    args = p.parse_args(argv)

    if args.watch:
        return watch(args.url, args.interval, args.out)
    if args.logfile:
        return analyze_file(
            args.logfile,
            avg_chars=args.avg_chars,
            price_per_million=args.price_per_million,
            usd_krw=args.usd_krw,
            csv_out=args.csv,
            md_out=args.md,
        )
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
