"""YAML 설정 파일 로더.

config/ 디렉토리의 YAML 파일을 읽어 dataclass로 검증 후 반환한다.
Databricks 환경의 pydantic 버전 충돌을 피하기 위해 dataclass + 수동 검증을 사용한다.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

_CONFIG_DIR = Path("config")


# ─────────────────────────────────────────
# Config 데이터 클래스 정의
# ─────────────────────────────────────────


@dataclass
class LLMConfig:
    """LLM 생성 모델 파라미터 (config/llm_config.yaml)."""

    temperature: float
    max_tokens: int
    model_label: str


@dataclass
class ChunkingConfig:
    """청킹 파라미터 (config/chunking_config.yaml)."""

    chunk_size: int
    chunk_overlap: int
    strategy: str


@dataclass
class RetrievalConfig:
    """벡터 검색 파라미터 (config/retrieval_config.yaml)."""

    top_k: int
    similarity_threshold: float
    enable_reranker: bool


@dataclass
class PromptTemplates:
    """프롬프트 템플릿 (config/prompt_templates.yaml)."""

    system_prompt: str
    user_prompt_template: str


# ─────────────────────────────────────────
# 검증 함수
# ─────────────────────────────────────────


def _validate_llm_config(cfg: LLMConfig) -> None:
    if not (0.0 <= cfg.temperature <= 2.0):
        raise ValueError(f"temperature는 0.0~2.0 범위여야 합니다. 입력값: {cfg.temperature}")
    if cfg.max_tokens < 1:
        raise ValueError(f"max_tokens는 1 이상이어야 합니다. 입력값: {cfg.max_tokens}")


def _validate_chunking_config(cfg: ChunkingConfig) -> None:
    if cfg.chunk_size < 100:
        raise ValueError(f"chunk_size는 100 이상이어야 합니다. 입력값: {cfg.chunk_size}")
    if cfg.chunk_overlap < 0:
        raise ValueError(f"chunk_overlap은 0 이상이어야 합니다. 입력값: {cfg.chunk_overlap}")
    if cfg.chunk_overlap >= cfg.chunk_size:
        raise ValueError(
            f"chunk_overlap({cfg.chunk_overlap})은 chunk_size({cfg.chunk_size})보다 작아야 합니다"
        )
    allowed = {"recursive", "sentence", "token"}
    if cfg.strategy not in allowed:
        raise ValueError(f"strategy는 {allowed} 중 하나여야 합니다. 입력값: '{cfg.strategy}'")


def _validate_retrieval_config(cfg: RetrievalConfig) -> None:
    if not (1 <= cfg.top_k <= 20):
        raise ValueError(f"top_k는 1~20 범위여야 합니다. 입력값: {cfg.top_k}")
    if not (0.0 <= cfg.similarity_threshold <= 1.0):
        raise ValueError(
            f"similarity_threshold는 0.0~1.0 범위여야 합니다. 입력값: {cfg.similarity_threshold}"
        )


def _validate_prompt_templates(cfg: PromptTemplates) -> None:
    if "{context}" not in cfg.user_prompt_template or "{question}" not in cfg.user_prompt_template:
        raise ValueError(
            "user_prompt_template에는 {context}와 {question} 플레이스홀더가 필요합니다"
        )


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
    data = _load_yaml("llm_config.yaml")
    cfg = LLMConfig(**data)
    _validate_llm_config(cfg)
    return cfg


def load_chunking_config() -> ChunkingConfig:
    """config/chunking_config.yaml을 읽어 ChunkingConfig로 반환한다."""
    data = _load_yaml("chunking_config.yaml")
    cfg = ChunkingConfig(**data)
    _validate_chunking_config(cfg)
    return cfg


def load_retrieval_config() -> RetrievalConfig:
    """config/retrieval_config.yaml을 읽어 RetrievalConfig로 반환한다."""
    data = _load_yaml("retrieval_config.yaml")
    cfg = RetrievalConfig(**data)
    _validate_retrieval_config(cfg)
    return cfg


def load_prompt_templates() -> PromptTemplates:
    """config/prompt_templates.yaml을 읽어 PromptTemplates로 반환한다."""
    data = _load_yaml("prompt_templates.yaml")
    cfg = PromptTemplates(**data)
    _validate_prompt_templates(cfg)
    return cfg
