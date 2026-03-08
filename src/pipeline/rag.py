"""RAG 파이프라인 모듈.

Vector Search 검색 + LLM 생성을 조합하는 파이프라인.
Databricks 노트북 및 Gradio UI에서 import하여 사용한다.

Note:
    databricks-vectorsearch 패키지는 namespace 충돌 문제로 사용하지 않는다.
    databricks-sdk의 w.vector_search_indexes.query_index() API를 사용한다.
    mlflow.deployments로 LLM 엔드포인트를 호출한다 (자격 증명 자동 처리).
"""

from dataclasses import dataclass, field
from typing import Any

from src.utils.config_loader import (
    load_llm_config,
    load_prompt_templates,
    load_retrieval_config,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# similarity_search 요청 컬럼 순서 (score는 응답에 자동 추가됨)
_SEARCH_COLUMNS = ["chunk_id", "doc_name", "doc_type", "page_number", "text"]


@dataclass
class RetrievedChunk:
    """검색된 단일 청크."""

    chunk_id: str
    doc_name: str
    doc_type: str
    page_number: int
    text: str
    score: float


@dataclass
class RAGResponse:
    """RAG 파이프라인 응답."""

    question: str
    answer: str
    chunks: list = field(default_factory=list)  # list[RetrievedChunk]
    retrieved_count: int = 0
    raw_count: int = 0


def _build_context(chunks: list) -> str:
    """검색된 청크들을 LLM 컨텍스트 문자열로 변환한다."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        header = (
            f"[출처 {i}] 문서: {chunk.doc_name} "
            f"| 유형: {chunk.doc_type} "
            f"| 페이지: {chunk.page_number}"
        )
        parts.append(f"{header}\n{chunk.text}")
    return "\n\n---\n\n".join(parts)


class RAGPipeline:
    """Retrieval-Augmented Generation 파이프라인.

    databricks-sdk로 Vector Search 검색을 수행하고,
    mlflow.deployments로 Claude Sonnet 답변을 생성한다.

    Args:
        vs_endpoint_name: Databricks Vector Search Endpoint 이름.
        vs_index_name: Vector Search Index 이름 (catalog.schema.index).
        llm_endpoint_name: Databricks Serving Endpoint 이름 (mlflow.deployments용).
    """

    def __init__(
        self,
        vs_endpoint_name: str,
        vs_index_name: str,
        llm_endpoint_name: str,
    ) -> None:
        self._vs_endpoint_name = vs_endpoint_name
        self._vs_index_name = vs_index_name
        self._llm_endpoint_name = llm_endpoint_name

        self._retrieval_cfg = load_retrieval_config()
        self._llm_cfg = load_llm_config()
        self._templates = load_prompt_templates()

        # lazy 초기화 — import 시 네트워크 호출 방지
        self._ws_client: Any = None
        self._deploy_client: Any = None

        logger.info(
            "RAGPipeline 초기화: vs_index=%s, llm=%s, top_k=%d, threshold=%.2f",
            vs_index_name,
            llm_endpoint_name,
            self._retrieval_cfg.top_k,
            self._retrieval_cfg.similarity_threshold,
        )

    # ── lazy 초기화 ─────────────────────────────────────────────────────────

    def _get_ws_client(self) -> Any:
        """WorkspaceClient를 lazy 반환 (databricks-sdk)."""
        if self._ws_client is None:
            from databricks.sdk import WorkspaceClient  # noqa: PLC0415

            self._ws_client = WorkspaceClient()
            logger.debug("WorkspaceClient 초기화 완료")
        return self._ws_client

    def _get_deploy_client(self) -> Any:
        """MLflow deployments 클라이언트를 lazy 반환."""
        if self._deploy_client is None:
            import mlflow.deployments  # noqa: PLC0415

            self._deploy_client = mlflow.deployments.get_deploy_client("databricks")
            logger.debug("MLflow deployments 클라이언트 초기화")
        return self._deploy_client

    # ── Public API ──────────────────────────────────────────────────────────

    def retrieve(self, question: str, top_k: int | None = None) -> list:
        """Vector Search로 관련 청크를 검색한다.

        Args:
            question: 검색 쿼리 문자열.
            top_k: 검색 결과 수. None이면 retrieval_config.yaml 값 사용.

        Returns:
            similarity_threshold 이상인 RetrievedChunk 리스트.
        """
        k = top_k if top_k is not None else self._retrieval_cfg.top_k
        threshold = self._retrieval_cfg.similarity_threshold

        logger.info("검색 시작: query='%.50s', top_k=%d, threshold=%.2f", question, k, threshold)

        w = self._get_ws_client()
        response = w.vector_search_indexes.query_index(
            index_name=self._vs_index_name,
            query_text=question,
            columns=_SEARCH_COLUMNS,
            num_results=k,
        )

        rows = response.result.data_array or []
        logger.debug("VS 원결과: %d건", len(rows))

        chunks = []
        for row in rows:
            # data_array 컬럼 순서: chunk_id, doc_name, doc_type, page_number, text, score
            chunk = RetrievedChunk(
                chunk_id=str(row[0]) if len(row) > 0 else "",
                doc_name=str(row[1]) if len(row) > 1 else "",
                doc_type=str(row[2]) if len(row) > 2 else "",
                page_number=int(row[3]) if len(row) > 3 else 0,
                text=str(row[4]) if len(row) > 4 else "",
                score=float(row[5]) if len(row) > 5 else 0.0,
            )
            if chunk.score >= threshold:
                chunks.append(chunk)

        logger.info(
            "검색 완료: 원결과 %d건 → threshold(%.2f) 필터 후 %d건",
            len(rows), threshold, len(chunks),
        )
        return chunks

    def generate(self, question: str, chunks: list) -> str:
        """검색된 청크를 컨텍스트로 LLM 답변을 생성한다.

        Args:
            question: 사용자 질의.
            chunks: retrieve()가 반환한 RetrievedChunk 리스트.

        Returns:
            LLM 생성 답변 문자열.
        """
        context = _build_context(chunks)
        user_prompt = self._templates.user_prompt_template.format(
            context=context,
            question=question,
        )

        logger.info(
            "생성 시작: llm=%s, chunks=%d개, context=%d자",
            self._llm_endpoint_name, len(chunks), len(context),
        )

        client = self._get_deploy_client()
        response = client.predict(
            endpoint=self._llm_endpoint_name,
            inputs={
                "messages": [
                    {"role": "system", "content": self._templates.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": self._llm_cfg.max_tokens,
                "temperature": self._llm_cfg.temperature,
            },
        )

        answer: str = response["choices"][0]["message"]["content"]
        logger.info("생성 완료: answer=%d자", len(answer))
        return answer

    def run(self, question: str) -> RAGResponse:
        """RAG 파이프라인 전체 실행 (검색 → 생성).

        Args:
            question: 사용자 질의.

        Returns:
            RAGResponse 인스턴스.
        """
        logger.info("RAG 실행: question='%.80s'", question)

        chunks = self.retrieve(question)

        if not chunks:
            logger.warning("검색 결과 없음: question='%.80s'", question)
            return RAGResponse(
                question=question,
                answer="제공된 문서에서 해당 정보를 찾을 수 없습니다.",
                chunks=[],
                retrieved_count=0,
                raw_count=0,
            )

        answer = self.generate(question, chunks)

        return RAGResponse(
            question=question,
            answer=answer,
            chunks=chunks,
            retrieved_count=len(chunks),
            raw_count=len(chunks),
        )
