"""练习模式接口。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.deps import CurrentUser, SessionDep
from app.schemas.envelope import ok
from app.services import exercise as exercise_service

router = APIRouter(prefix="/api/exercise", tags=["练习模式"])


class GenerateRequest(BaseModel):
    """出题请求。"""

    type: str = Field(default="step_identify")
    difficulty: str = Field(default="easy")


class SubmitRequest(BaseModel):
    """判分请求。"""

    exercise_id: int = Field(alias="exerciseId", ge=1)
    answer: str = Field(min_length=1, max_length=64)

    model_config = {"populate_by_name": True}


@router.post("/generate")
def generate(payload: GenerateRequest, session: SessionDep, user: CurrentUser) -> dict:
    """生成一道练习题。"""
    return ok(
        exercise_service.generate(session, payload.type, payload.difficulty)
    )


@router.post("/submit")
def submit(payload: SubmitRequest, session: SessionDep, user: CurrentUser) -> dict:
    """提交答案并返回判分结果。"""
    return ok(
        exercise_service.submit(
            session, user.id, payload.exercise_id, payload.answer
        )
    )


@router.get("/types")
def list_types() -> dict:
    """返回支持的题型，供前端渲染选择器。"""
    return ok(
        [
            {"type": "step_identify", "label": "步骤识别"},
            {"type": "cell_result", "label": "结果填写"},
            {"type": "key_param", "label": "参数调试"},
        ]
    )