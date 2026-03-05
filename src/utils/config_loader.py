"""YAML 설정 파일 로더.

config/ 디렉토리의 YAML 파일을 읽어 Pydantic v2 모델로 검증 후 반환한다.
잘못된 값은 ValidationError로 누락 키/타입 불일치를 명확히 출력한다.
"""

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_CONFIG_DIR = Path("config")


# ─────────────────────────────────────────
# Pydantic 모델 정의
# ─────────────────────────────────────────


class LLMConfig(BaseModel):
    """LLM 생성 모델 파라미터 (config/llm_config.yaml)."""

    temperature: Annotated[float, Field(ge=0.0, le=2.0)]
    max_tokens: Annotated[int, Field(ge=1)]
    model_label: str


class ChunkingConfig(BaseModel):
    """청킹 파라미터 (config/chunking_config.yaml)."""

    chunk_size: Annotated[int, Field(ge=100)]
    chunk_overlap: Annotated[int, Field(ge=0)]
    strategy: str

    @model_validator(mode="after")
    def overlap_must_be_less_than_size(self) -> "ChunkingConfig":
        if self.chunk_overlap >= self.chunk_size:
            msg = f"chunk_overlap({self.chunk_overlap})은 chunk_size({self.chunk_size})보다 작아야 합니다"
            raise ValueError(msg)
        return self

    @field_validator("strategy")
    @classmethod
    def strategy_must_be_valid(cls, v: str) -> str:
        allowed = {"recursive", "sentence", "token"}
        if v not in allowed:
            msg = f"strategy는 {allowed} 중 하나여야 합니다. 입력값: '{v}'"
            raise ValueError(msg)
        return v


class RetrievalConfig(BaseModel):
    """벡터 검색 파라미터 (config/retrieval_config.yaml)."""

    top_k: Annotated[int, Field(ge=1, le=20)]
    similarity_threshold: Annotated[float, Field(ge=0.0, le=1.0)]
    enable_reranker: bool


class PromptTemplates(BaseModel):
    """프롬프트 템플릿 (config/prompt_templates.yaml)."""

    system_prompt: str
    user_prompt_template: str

    @field_validator("user_prompt_template")
    @classmethod
    def template_must_have_placeholders(cls, v: str) -> str:
        if "{context}" not in v or "{question}" not in v:
            msg = "user_prompt_template에는 {context}와 {question} 플레이스홀더가 필요합니다"
            raise ValueError(msg)
        return v


# ─────────────────────────────────────────
# 로더 함수
# ─────────────────────────────────────────


def _load_yaml(file_name: str) -> dict:  # type: ignore[type-arg]
    """YAML 파일을 읽어 딕셔너리로 반환한다."""
    path = _CONFIG_DIR / file_name
    if not path.exists():
        msg = f"설정 파일을 찾을 수 없습니다: {path}"
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_llm_config() -> LLMConfig:
    """config/llm_config.yaml을 읽어 LLMConfig로 반환한다."""
    return LLMConfig(**_load_yaml("llm_config.yaml"))


def load_chunking_config() -> ChunkingConfig:
    """config/chunking_config.yaml을 읽어 ChunkingConfig로 반환한다."""
    return ChunkingConfig(**_load_yaml("chunking_config.yaml"))


def load_retrieval_config() -> RetrievalConfig:
    """config/retrieval_config.yaml을 읽어 RetrievalConfig로 반환한다."""
    return RetrievalConfig(**_load_yaml("retrieval_config.yaml"))


def load_prompt_templates() -> PromptTemplates:
    """config/prompt_templates.yaml을 읽어 PromptTemplates로 반환한다."""
    return PromptTemplates(**_load_yaml("prompt_templates.yaml"))
