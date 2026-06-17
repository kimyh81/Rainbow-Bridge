"""LLM 호출 로그(`llm_logs`) 스키마 + 저장 헬퍼.

`GET /api/v1/admin/usage` 가 집계해 보여줄 원본 로그입니다. 지금은 실제 저장
구조가 없어서, 호출 한 건을 표준 형태로 적재하는 스키마/헬퍼를 정의합니다.

⚠️ 개인정보 최소화 (../CLAUDE.md, ../llm/CLAUDE.md §5):
   **대화 원문(프롬프트/응답 텍스트)은 저장하지 않습니다.** 위기 로그는 특히
   등급·신호 위주로만. 길이·토큰·지연 같은 비식별 지표만 남깁니다.

ℹ️ MongoDB 연결은 백엔드(김윤한) 담당입니다. 이 모듈은 컬렉션 핸들을
   **주입받아** 저장만 하므로 백엔드 db 모듈에 의존하지 않습니다.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Final, Iterator, Optional

# 컬렉션 이름 — 백엔드와 합의해 고정.
COLLECTION: Final[str] = "llm_logs"

# 호출 종류 (어떤 기능에서 LLM을 불렀는지)
KIND_MESSAGE: Final[str] = "message"  # ③ 추모 메시지
KIND_MISSION: Final[str] = "mission"  # ⑤ 미션 추천
KIND_CRISIS: Final[str] = "crisis"  # ⑦ 위기 감지
KIND_VET_PROTOCOL: Final[str] = "vet_protocol"  # 수의사 처치 안내 RAG (triage 생성기능 드랍 후 재용도)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class LLMLog:
    """LLM 호출 한 건의 비식별 로그.

    원문 텍스트는 담지 않습니다(개인정보 최소화). 집계(build_report)와
    사용량 대시보드(admin/usage)의 단위가 됩니다.
    """

    kind: str  # KIND_* 중 하나
    provider: str  # gemini | perso | ollama
    model: str  # 예: gemini-2.5-flash
    pet_id: Optional[str] = None  # 반려동물별 집계용 (없으면 전체)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    ok: bool = True  # 호출 성공 여부
    risk_level: Optional[int] = None  # ⑦ 위기 등급(L0~L3)만 — 원문은 저장 ❌
    created_at: datetime = field(default_factory=_now)

    @property
    def total_tokens(self) -> int:
        """입력+출력 토큰 합 — 백엔드 admin/usage 의 `$sum: total_tokens` 와 정합."""
        return self.tokens_in + self.tokens_out

    def to_doc(self) -> dict[str, Any]:
        """MongoDB 저장용 dict.

        admin/usage 집계가 `total_tokens` 로 합산하므로 그 필드를 포함합니다.
        ⚠️ 대화 원문(prompt/응답 텍스트)은 저장하지 않습니다(개인정보 최소화).
        """
        doc = asdict(self)
        doc["total_tokens"] = self.total_tokens
        return doc

    @classmethod
    def from_openai(
        cls,
        resp: Any,
        *,
        kind: str,
        pet_id: Optional[str] = None,
        provider: str = "gemini",
        model: Optional[str] = None,
        latency_ms: int = 0,
        ok: bool = True,
        risk_level: Optional[int] = None,
    ) -> "LLMLog":
        """OpenAI 호환 응답 객체에서 비식별 로그를 만듭니다.

        토큰은 `resp.usage` 에서 **가드해서** 꺼냅니다(없으면 0). 원문 텍스트는
        절대 담지 않습니다(개인정보 최소화). 호출 실패로 응답이 없으면 `resp=None`
        으로 넘기고 `ok=False` 로 적재하세요(토큰 0).

        Args:
            resp: OpenAI 호환 ChatCompletion 응답(실패 시 None 허용).
            kind: KIND_* 중 하나(어느 기능에서 불렀는지).
            model: 인자 우선, 없으면 응답의 model 사용.
        """
        usage = getattr(resp, "usage", None) if resp is not None else None
        tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)
        resolved_model = model or (
            getattr(resp, "model", "") if resp is not None else ""
        )
        return cls(
            kind=kind,
            provider=provider,
            model=resolved_model or "",
            pet_id=pet_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            ok=ok,
            risk_level=risk_level,
        )


class _LatencyTimer:
    """경과 시간(ms)을 보관. 블록 종료 후 `.ms` 가 확정됩니다."""

    ms: int = 0


@contextmanager
def measure_latency() -> Iterator[_LatencyTimer]:
    """LLM 호출 지연을 ms 로 측정하는 컨텍스트.

    사용:
        with measure_latency() as t:
            resp = client.chat.completions.create(...)
        log = LLMLog.from_openai(resp, kind=KIND_MESSAGE, latency_ms=t.ms)

    예외가 나도 `finally` 에서 경과가 기록되므로 실패(ok=False) 로깅에도 안전합니다.
    """
    timer = _LatencyTimer()
    start = time.perf_counter()
    try:
        yield timer
    finally:
        timer.ms = int((time.perf_counter() - start) * 1000)


def save_log(collection: Any, log: LLMLog) -> Any:
    """로그 한 건을 컬렉션에 저장하고 insert 결과를 돌려줍니다.

    Args:
        collection: pymongo/motor 컬렉션 핸들(백엔드가 주입).
        log: 저장할 LLMLog.

    Note:
        동기 pymongo 기준입니다. 백엔드가 motor(async)면 호출부에서
        `await collection.insert_one(log.to_doc())` 로 직접 쓰세요.
    """
    return collection.insert_one(log.to_doc())


def log_llm_call(
    collection: Any,
    resp: Any,
    *,
    kind: str,
    latency_ms: int,
    ok: bool = True,
    pet_id: Optional[str] = None,
    provider: str = "gemini",
    model: Optional[str] = None,
    risk_level: Optional[int] = None,
) -> Any:
    """응답 → 로그 변환 + 저장을 한 번에(동기 컬렉션용). 호출부에서 진짜 1줄.

    `from_openai` 로 LLMLog 를 만들고 `save_log` 로 저장합니다.

    ⚠️ best-effort 로 쓰세요: 로그 저장 실패가 **사용자 응답을 깨면 안 됩니다.**
    호출부에서 `try/except Exception: pass` 로 감싸세요.

    Note:
        동기 pymongo 기준. 백엔드 motor(async)면 이 함수 대신
        `await collection.insert_one(LLMLog.from_openai(...).to_doc())` 를 쓰세요.
    """
    log = LLMLog.from_openai(
        resp,
        kind=kind,
        pet_id=pet_id,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        ok=ok,
        risk_level=risk_level,
    )
    return save_log(collection, log)


async def alog_llm_call(
    collection: Any,
    *,
    kind: str,
    latency_ms: int,
    ok: bool = True,
    pet_id: Optional[str] = None,
    provider: str = "gemini",
    model: Optional[str] = None,
    risk_level: Optional[int] = None,
    resp: Any = None,
) -> Any:
    """`log_llm_call` 의 motor(async) 버전 — 백엔드 호출부에서 진짜 1줄.

    `resp` 가 없어도(None) 동작합니다(토큰 0). 토큰을 빼고 **횟수·종류·지연·
    성공여부**만 남기는 라이트 로깅에 그대로 맞습니다. 토큰까지 남기려면 OpenAI
    호환 응답 객체를 `resp` 로 넘기세요.

    ⚠️ best-effort 로 쓰세요: 로그 저장 실패가 **사용자 응답을 깨면 안 됩니다.**
    호출부에서 `try/except Exception: pass` 로 감싸세요.
    """
    log = LLMLog.from_openai(
        resp,
        kind=kind,
        pet_id=pet_id,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        ok=ok,
        risk_level=risk_level,
    )
    return await collection.insert_one(log.to_doc())
