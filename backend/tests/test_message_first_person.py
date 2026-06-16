"""create_message 의 1인칭 게이트 연결 단위 테스트.

핵심: first_person = request_first_person AND recovery.allow_first_person.
외부 의존(LLM·DB)은 모두 모킹하고, generate_message 가 받는 first_person 만 핀다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

from app.schemas.message import MessageCreate
from app.services import message as message_svc

_PET_ID = "0123456789abcdef01234567"


def _fake_mongo():
    """pets.find_one / messages.insert_one / update_one / llm_logs 를 흉내."""
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value={"_id": ObjectId(_PET_ID), "name": "별"})
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    coll.update_one = AsyncMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    mongo = MagicMock()
    mongo.db = db
    return mongo


def _recovery(*, allow: bool, unlocked: bool = True):
    return MagicMock(content_unlocked=unlocked, allow_first_person=allow)


async def _run(*, request_first_person: bool, allow_first_person: bool):
    """공통 실행 — generate_message 가 받은 first_person 과 응답을 돌려준다."""
    gen_msg = MagicMock(
        return_value={
            "content": "추억의 편지",
            "tone": "warm",
            "source": "local",
            "first_person": True,
        }
    )
    with (
        patch.object(message_svc, "mongodb", new=_fake_mongo()),
        patch.object(
            message_svc, "get_recent_emotions", new=AsyncMock(return_value=[])
        ),
        patch.object(
            message_svc,
            "get_recovery",
            new=AsyncMock(return_value=_recovery(allow=allow_first_person)),
        ),
        patch.object(
            message_svc,
            "assess_crisis",
            new=MagicMock(return_value=MagicMock(risk_level=0)),
        ),
        patch.object(message_svc, "generate_message", new=gen_msg),
        patch.object(message_svc, "alog_llm_call", new=AsyncMock()),
    ):
        resp = await message_svc.create_message(
            MessageCreate(pet_id=_PET_ID, request_first_person=request_first_person)
        )
    return gen_msg.call_args.kwargs["first_person"], resp


@pytest.mark.asyncio
async def test_first_person_true_when_requested_and_gate_open():
    passed, resp = await _run(request_first_person=True, allow_first_person=True)
    assert passed is True
    assert resp.first_person is True
    assert resp.allow_first_person is True
    assert resp.content_unlocked is True


@pytest.mark.asyncio
async def test_first_person_false_when_gate_closed():
    """요청해도 게이트(allow_first_person=False)면 1인칭 잠금."""
    passed, resp = await _run(request_first_person=True, allow_first_person=False)
    assert passed is False
    assert resp.first_person is False
    assert resp.allow_first_person is False


@pytest.mark.asyncio
async def test_first_person_false_when_not_requested():
    """게이트 열려도 요청 안 하면 3인칭."""
    passed, resp = await _run(request_first_person=False, allow_first_person=True)
    assert passed is False
    assert resp.first_person is False
