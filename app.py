"""제약 SOP/QMS RAG 채팅 UI.

Databricks Vector Search + Claude Sonnet 기반 RAG 파이프라인의
로컬 확인용 Gradio 5.x 채팅 인터페이스.

실행:
    just run-ui
    또는
    uv run python app.py
"""

from __future__ import annotations

import os
from collections.abc import Generator

import gradio as gr
from dotenv import load_dotenv

from src.pipeline.rag import RAGPipeline, RAGResponse, RetrievedChunk
from src.utils.logger import get_logger

# ─────────────────────────────────────────
# 초기화
# ─────────────────────────────────────────

load_dotenv()
logger = get_logger(__name__)

# ─────────────────────────────────────────
# 상수 (매직 문자열 방지)
# ─────────────────────────────────────────

_APP_TITLE = "제약 SOP/QMS 문서 검색 도우미"
_APP_DESCRIPTION = "Databricks Vector Search + Claude Sonnet 기반 RAG 시스템"
_SOURCE_PREVIEW_LENGTH = 200

_DEFAULT_VS_ENDPOINT = "shrag-vs-endpoint"
_DEFAULT_VS_INDEX = "shtest.ragtest.chunks_index"
_DEFAULT_LLM_ENDPOINT = "databricks-claude-sonnet"

_ENV_VS_ENDPOINT = "DATABRICKS_VECTOR_SEARCH_ENDPOINT"
_ENV_VS_INDEX = "DATABRICKS_VECTOR_INDEX_NAME"
_ENV_LLM_ENDPOINT = "DATABRICKS_LLM_ENDPOINT"

_MSG_LOADING = "🔍 문서를 검색하고 있습니다..."
_MSG_EMPTY_INPUT = "질문을 입력해 주세요."
_MSG_PIPELINE_ERROR = (
    "⚠️ RAG 파이프라인을 초기화할 수 없습니다.\n\n"
    "환경변수를 확인하세요:\n"
    "- `DATABRICKS_HOST`\n"
    "- `DATABRICKS_TOKEN`\n"
    "- `DATABRICKS_VECTOR_SEARCH_ENDPOINT`\n"
    "- `DATABRICKS_VECTOR_INDEX_NAME`\n"
    "- `DATABRICKS_LLM_ENDPOINT`"
)
_MSG_QUERY_ERROR = "⚠️ 질문 처리 중 오류가 발생했습니다: {error}"

_HTML_SOURCES_EMPTY = (
    "<p style='color: #94a3b8; text-align: center; padding: 20px;'>"
    "질문을 입력하면 참조 문서가 여기에 표시됩니다.</p>"
)

# ─────────────────────────────────────────
# 환경변수 파싱
# ─────────────────────────────────────────


def _parse_llm_endpoint_name(raw: str) -> str:
    """환경변수에서 LLM 엔드포인트 이름을 추출한다.

    .env에 full URL(https://.../serving-endpoints/{name}/invocations) 또는
    엔드포인트 이름만 저장될 수 있으므로 두 형식을 모두 처리한다.
    """
    raw = raw.strip()
    if not raw.startswith("http"):
        return raw  # 이미 이름 형식

    # https://adb-xxx.net/serving-endpoints/{name}/invocations 패턴 파싱
    try:
        parts = raw.rstrip("/").split("/")
        serving_idx = parts.index("serving-endpoints")
        return parts[serving_idx + 1]
    except (ValueError, IndexError):
        logger.warning("LLM 엔드포인트 URL 파싱 실패, 원본값 사용: %s", raw)
        return raw


def _load_pipeline_config() -> tuple[str, str, str]:
    """환경변수에서 RAGPipeline 생성 인자를 로드한다."""
    # 빈 문자열("")도 설정 누락으로 간주하여 기본값 사용
    vs_endpoint = os.getenv(_ENV_VS_ENDPOINT) or _DEFAULT_VS_ENDPOINT
    vs_index = os.getenv(_ENV_VS_INDEX) or _DEFAULT_VS_INDEX
    llm_raw = os.getenv(_ENV_LLM_ENDPOINT) or _DEFAULT_LLM_ENDPOINT
    llm_endpoint = _parse_llm_endpoint_name(llm_raw)

    logger.info(
        "파이프라인 설정 로드: vs_endpoint=%s, vs_index=%s, llm=%s",
        vs_endpoint,
        vs_index,
        llm_endpoint,
    )
    return vs_endpoint, vs_index, llm_endpoint


# ─────────────────────────────────────────
# RAGPipeline 싱글턴
# ─────────────────────────────────────────

_pipeline: RAGPipeline | None = None
_pipeline_init_error: str | None = None


def _get_pipeline() -> RAGPipeline | None:
    """RAGPipeline 싱글턴을 반환한다. 초기화 실패 시 None을 반환한다."""
    global _pipeline, _pipeline_init_error

    if _pipeline is not None:
        return _pipeline
    if _pipeline_init_error is not None:
        return None

    try:
        vs_endpoint, vs_index, llm_endpoint = _load_pipeline_config()
        _pipeline = RAGPipeline(
            vs_endpoint_name=vs_endpoint,
            vs_index_name=vs_index,
            llm_endpoint_name=llm_endpoint,
        )
        logger.info("RAGPipeline 싱글턴 초기화 완료")
        return _pipeline
    except Exception as exc:
        _pipeline_init_error = str(exc)
        logger.error("RAGPipeline 초기화 실패: %s", exc, exc_info=True)
        return None


# ─────────────────────────────────────────
# 참조 출처 HTML 렌더링
# ─────────────────────────────────────────


def _render_chunk_card(chunk: RetrievedChunk, index: int) -> str:
    """단일 청크를 HTML 카드로 렌더링한다."""
    preview = chunk.text[:_SOURCE_PREVIEW_LENGTH]
    if len(chunk.text) > _SOURCE_PREVIEW_LENGTH:
        preview += "..."

    # 유사도 점수에 따른 배지 색상
    if chunk.score >= 0.7:
        score_color = "#22c55e"  # 초록
    elif chunk.score >= 0.5:
        score_color = "#f59e0b"  # 주황
    else:
        score_color = "#64748b"  # 회색

    score_pct = int(chunk.score * 100)

    return (
        f"<div style='"
        f"border:1px solid #e2e8f0;border-radius:8px;padding:12px;"
        f"margin-bottom:10px;background:#fafafa;font-size:13px;'>"
        f"<div style='display:flex;justify-content:space-between;"
        f"align-items:center;margin-bottom:6px;'>"
        f"<span style='font-weight:600;color:#1e293b;'>[{index}] {chunk.doc_name}</span>"
        f"<span style='font-size:11px;font-weight:600;color:{score_color};"
        f"background:{score_color}18;padding:2px 8px;border-radius:12px;'>"
        f"{score_pct}%</span></div>"
        f"<div style='color:#64748b;margin-bottom:6px;'>"
        f"{chunk.doc_type} | {chunk.page_number}p</div>"
        f"<div style='color:#374151;line-height:1.5;"
        f"border-top:1px solid #e2e8f0;padding-top:8px;'>{preview}</div>"
        f"</div>"
    )


def _build_sources_html(chunks: list[RetrievedChunk]) -> str:
    """검색된 청크 목록을 참조 출처 HTML로 변환한다."""
    if not chunks:
        return _HTML_SOURCES_EMPTY

    header = (
        f"<div style='margin-bottom:10px;font-size:13px;"
        f"color:#64748b;font-weight:500;'>"
        f"참조 출처 {len(chunks)}건</div>"
    )
    cards = "".join(_render_chunk_card(chunk, i) for i, chunk in enumerate(chunks, 1))
    return header + cards


# ─────────────────────────────────────────
# RAG 실행
# ─────────────────────────────────────────


def respond(message: str) -> tuple[str, str]:
    """사용자 질문을 RAG 파이프라인에 전달하고 (answer, sources_html)을 반환한다."""
    pipeline = _get_pipeline()

    if pipeline is None:
        return _MSG_PIPELINE_ERROR, _HTML_SOURCES_EMPTY

    try:
        response: RAGResponse = pipeline.run(message)
        sources_html = _build_sources_html(response.chunks)
        logger.info(
            "응답 완료: retrieved=%d, answer_len=%d",
            response.retrieved_count,
            len(response.answer),
        )
        return response.answer, sources_html
    except Exception as exc:
        logger.error("RAG 실행 오류: %s", exc, exc_info=True)
        return _MSG_QUERY_ERROR.format(error=exc), _HTML_SOURCES_EMPTY


# ─────────────────────────────────────────
# Gradio 이벤트 핸들러
# ─────────────────────────────────────────


def handle_submit(
    user_message: str,
    history: list[dict],
) -> Generator[tuple[list[dict], list[dict], str, str], None, None]:
    """사용자 메시지를 받아 RAG 응답과 출처 HTML을 반환하는 Generator.

    첫 번째 yield에서 "검색 중..." 상태를 즉시 표시하고,
    두 번째 yield에서 최종 결과를 반환한다.

    Outputs 순서: (chatbot, history_state, msg_input, sources_display)
    """
    stripped = user_message.strip()
    if not stripped:
        yield history, history, user_message, _HTML_SOURCES_EMPTY
        return

    # 1단계: 사용자 메시지 + 처리 중 상태 즉시 표시
    interim_history = history + [
        {"role": "user", "content": stripped},
        {"role": "assistant", "content": _MSG_LOADING},
    ]
    yield interim_history, history, "", _HTML_SOURCES_EMPTY

    # 2단계: RAG 실행
    answer, sources_html = respond(stripped)

    # 3단계: 최종 결과로 교체 + 히스토리 상태 갱신
    final_history = history + [
        {"role": "user", "content": stripped},
        {"role": "assistant", "content": answer},
    ]
    yield final_history, final_history, "", sources_html


# ─────────────────────────────────────────
# Gradio UI 빌드
# ─────────────────────────────────────────


def build_ui() -> gr.Blocks:
    """Gradio 5.x Blocks 기반 채팅 UI를 구성한다.

    레이아웃:
        좌측 채팅 영역 (scale=2) + 우측 참조 출처 패널 (scale=1)
    """
    with gr.Blocks(
        title=_APP_TITLE,
        fill_height=True,
    ) as demo:
        gr.Markdown(f"## {_APP_TITLE}")
        gr.Markdown(f"*{_APP_DESCRIPTION}*")

        with gr.Row(equal_height=True):
            # ── 좌측: 채팅 영역 ──────────────────────────────
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    label="대화",
                    type="messages",
                    height=520,
                    allow_tags=False,
                )
                with gr.Row():
                    msg_input = gr.Textbox(
                        placeholder="SOP/QMS 문서에 대해 질문하세요. 예: GMP 원료 수입 절차는?",
                        show_label=False,
                        scale=9,
                        autofocus=True,
                        lines=1,
                        max_lines=4,
                        container=False,
                    )
                    submit_btn = gr.Button(
                        "전송",
                        variant="primary",
                        scale=1,
                        min_width=70,
                    )
                clear_btn = gr.Button("대화 초기화", variant="secondary", size="sm")

            # ── 우측: 참조 출처 패널 ─────────────────────────
            with gr.Column(scale=1):
                gr.Markdown("### 참조 출처")
                sources_display = gr.HTML(value=_HTML_SOURCES_EMPTY)

        # ── 히스토리 State ────────────────────────────────────
        history_state: gr.State = gr.State([])

        # ── 이벤트 연결 ──────────────────────────────────────
        submit_inputs = [msg_input, history_state]
        submit_outputs = [chatbot, history_state, msg_input, sources_display]

        msg_input.submit(
            fn=handle_submit,
            inputs=submit_inputs,
            outputs=submit_outputs,
        )
        submit_btn.click(
            fn=handle_submit,
            inputs=submit_inputs,
            outputs=submit_outputs,
        )
        clear_btn.click(
            fn=lambda: ([], [], "", _HTML_SOURCES_EMPTY),
            inputs=None,
            outputs=submit_outputs,
        )

    return demo


# ─────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────

if __name__ == "__main__":
    ui = build_ui()
    ui.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
