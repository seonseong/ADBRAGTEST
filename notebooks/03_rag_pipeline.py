# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # 03. RAG 파이프라인 — 검색 + 생성
# MAGIC
# MAGIC 이 노트북은 Vector Search 검색과 Claude Sonnet LLM 생성을 연결하여
# MAGIC 제약 SOP/QMS 문서 기반 RAG 파이프라인을 검증합니다.
# MAGIC
# MAGIC **아키텍처:**
# MAGIC ```
# MAGIC 사용자 질문
# MAGIC     └─▶ [Retrieve] Vector Search (embedding-bge-m3)
# MAGIC              └─▶ similarity_threshold 필터링
# MAGIC                       └─▶ [Generate] Claude Sonnet 4.5
# MAGIC                                └─▶ 답변 + 출처
# MAGIC ```
# MAGIC
# MAGIC **실행 전 체크리스트:**
# MAGIC - [ ] 02_embedding.py 완료 → Vector Search Index ONLINE 상태
# MAGIC - [ ] `embedding-bge-m3` Serving Endpoint 활성화
# MAGIC - [ ] `databricks-claude-sonnet-4-5` Serving Endpoint 활성화

# COMMAND ----------
# MAGIC %md ## 셀 1: 의존성 확인

# COMMAND ----------

# databricks-sdk는 클러스터 라이브러리로 이미 설치됨 → %pip install 불필요
# databricks-vectorsearch 패키지 namespace 충돌 문제 → SDK API로 대체
# mlflow는 Databricks Runtime에 기본 포함
print("클러스터 라이브러리 사용 — 추가 설치 불필요")

# COMMAND ----------
# MAGIC %md ## 셀 2: PROJECT_ROOT 설정

# COMMAND ----------

import sys
import os

try:
    _nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    PROJECT_ROOT = "/Workspace" + "/".join(_nb_path.split("/")[:-2])
except Exception:
    PROJECT_ROOT = "/Workspace/Repos/shseo@in4ucloud.com/ADBRAGTEST"

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.chdir(PROJECT_ROOT)

print(f"프로젝트 루트: {PROJECT_ROOT}")

# COMMAND ----------
# MAGIC %md ## 셀 3: 상수 정의

# COMMAND ----------

from src.utils.logger import get_logger
from src.utils.config_loader import load_retrieval_config, load_llm_config

logger = get_logger("03_rag_pipeline")

VS_ENDPOINT_NAME  = "shrag-vs-endpoint"
VS_INDEX_NAME     = "shtest.ragtest.chunks_index"
LLM_ENDPOINT_NAME = "databricks-claude-sonnet-4-5"

retrieval_cfg = load_retrieval_config()
llm_cfg       = load_llm_config()

print(f"VS Endpoint  : {VS_ENDPOINT_NAME}")
print(f"VS Index     : {VS_INDEX_NAME}")
print(f"LLM Endpoint : {LLM_ENDPOINT_NAME}")
print()
print(f"top_k               : {retrieval_cfg.top_k}")
print(f"similarity_threshold: {retrieval_cfg.similarity_threshold}")
print(f"temperature         : {llm_cfg.temperature}")
print(f"max_tokens          : {llm_cfg.max_tokens}")

# COMMAND ----------
# MAGIC %md ## 셀 4: Vector Search 인덱스 상태 확인

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
idx_obj = w.vector_search_indexes.get_index(index_name=VS_INDEX_NAME)

status = idx_obj.status
if status is None:
    raise RuntimeError("인덱스 상태를 읽을 수 없습니다.")

raw_state = getattr(status, "detailed_state", None) or getattr(status, "state", "UNKNOWN")
state = raw_state.value if hasattr(raw_state, "value") else str(raw_state)

try:
    idx_dict    = idx_obj.as_dict()
    indexed_rows = idx_dict.get("status", {}).get("indexed_row_count", "?")
except Exception:
    indexed_rows = "?"

print(f"인덱스 상태  : {state}")
print(f"인덱싱된 청크: {indexed_rows}개")

if "ONLINE" not in state:
    raise RuntimeError(
        f"인덱스가 ONLINE 상태가 아닙니다: {state}\n"
        "02_embedding.py 셀 7 완료 후 다시 실행하세요."
    )

logger.info("VS Index 확인: state=%s, indexed=%s", state, indexed_rows)
print("\nVector Search 인덱스 정상 확인 완료")

# COMMAND ----------
# MAGIC %md ## 셀 5: LLM 연결 테스트

# COMMAND ----------

import mlflow.deployments

deploy_client = mlflow.deployments.get_deploy_client("databricks")

_test_resp = deploy_client.predict(
    endpoint=LLM_ENDPOINT_NAME,
    inputs={
        "messages": [{"role": "user", "content": "안녕하세요. 연결 테스트입니다. 짧게 응답해주세요."}],
        "max_tokens": 50,
        "temperature": 0.0,
    },
)
_test_answer = _test_resp["choices"][0]["message"]["content"]

print(f"LLM 연결 성공!")
print(f"응답: {_test_answer}")
logger.info("LLM 연결 테스트 성공: endpoint=%s", LLM_ENDPOINT_NAME)

# COMMAND ----------
# MAGIC %md ## 셀 6: RAG 파이프라인 초기화

# COMMAND ----------

from src.pipeline.rag import RAGPipeline

pipeline = RAGPipeline(
    vs_endpoint_name=VS_ENDPOINT_NAME,
    vs_index_name=VS_INDEX_NAME,
    llm_endpoint_name=LLM_ENDPOINT_NAME,
)

print("RAG 파이프라인 초기화 완료")

# COMMAND ----------
# MAGIC %md ## 셀 7: 단건 쿼리 테스트

# COMMAND ----------

def print_rag_result(response) -> None:
    """RAGResponse를 보기 좋게 출력한다."""
    print("=" * 70)
    print(f"질문: {response.question}")
    print("=" * 70)
    print()
    print(f"[답변] (참조 청크: {response.retrieved_count}개)")
    print(response.answer)
    print()
    if response.chunks:
        print("[참조 출처]")
        for i, chunk in enumerate(response.chunks, 1):
            print(f"  [{i}] {chunk.doc_name} | 페이지 {chunk.page_number} | score={chunk.score:.4f}")
    print("=" * 70)


TEST_QUESTION = "GMP 준수를 위한 원료 수입 절차는 어떻게 되나요?"

result = pipeline.run(TEST_QUESTION)
print_rag_result(result)

# COMMAND ----------
# MAGIC %md ## 셀 8: 다건 쿼리 배치 테스트

# COMMAND ----------

BATCH_QUESTIONS = [
    "이탈(deviation) 발생 시 조사 및 보고 절차를 설명해주세요.",
    "세척 밸리데이션의 합격 기준은 무엇인가요?",
    "변경 관리(Change Control) 프로세스 단계를 설명해주세요.",
    "완제품 출하 전 품질 검토 항목은 무엇인가요?",
]

batch_results = []

for i, question in enumerate(BATCH_QUESTIONS, 1):
    print(f"\n[{i}/{len(BATCH_QUESTIONS)}] 처리 중: {question[:50]}...")
    response = pipeline.run(question)
    batch_results.append(response)
    print(f"  → 답변 {len(response.answer)}자, 참조 청크 {response.retrieved_count}개")

print(f"\n\n배치 테스트 완료: {len(batch_results)}건")

# COMMAND ----------
# MAGIC %md ## 셀 9: 배치 결과 상세 출력

# COMMAND ----------

for response in batch_results:
    print_rag_result(response)
    print()

# COMMAND ----------
# MAGIC %md ## 셀 10: 파이프라인 통계 요약

# COMMAND ----------

all_results = [result] + batch_results

total          = len(all_results)
no_result_cnt  = sum(1 for r in all_results if r.retrieved_count == 0)
avg_chunks     = sum(r.retrieved_count for r in all_results) / max(total, 1)
avg_answer_len = sum(len(r.answer) for r in all_results) / max(total, 1)

print("=" * 60)
print("RAG 파이프라인 검증 결과 요약")
print("=" * 60)
print(f"총 테스트 쿼리 수   : {total}건")
print(f"검색 결과 없음      : {no_result_cnt}건")
print(f"평균 참조 청크 수   : {avg_chunks:.1f}개")
print(f"평균 답변 길이      : {avg_answer_len:.0f}자")
print()
print("설정 파라미터:")
print(f"  similarity_threshold : {retrieval_cfg.similarity_threshold}")
print(f"  top_k                : {retrieval_cfg.top_k}")
print(f"  temperature          : {llm_cfg.temperature}")
print(f"  max_tokens           : {llm_cfg.max_tokens}")

if no_result_cnt > 0:
    print(f"\n경고: {no_result_cnt}건 검색 결과 없음 — retrieval_config.yaml의 similarity_threshold 낮추는 것 고려")

logger.info(
    "파이프라인 검증 완료: total=%d, no_result=%d, avg_chunks=%.1f",
    total, no_result_cnt, avg_chunks,
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 완료
# MAGIC
# MAGIC RAG 파이프라인 검증이 완료되었습니다.
# MAGIC
# MAGIC **다음 단계:**
# MAGIC - `notebooks/04_evaluation.py` — RAGAS 기반 RAG 품질 평가 (선택)
# MAGIC - `app/gradio_app.py` — Gradio UI 구성 및 로컬 테스트
