# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # 02. 임베딩 생성 및 Vector Search 인덱스 구축
# MAGIC
# MAGIC 이 노트북은 Delta Table(`shtest.ragtest.chunks`)을 소스로 삼아
# MAGIC Databricks Vector Search Delta Sync Index를 생성하고 동기화합니다.
# MAGIC
# MAGIC **아키텍처:**
# MAGIC ```
# MAGIC chunks (Delta Table, CDF 활성화)
# MAGIC     └─▶ Vector Search Delta Sync Index
# MAGIC              ├─ embedding model : embedding-bge-m3 (Managed Embedding)
# MAGIC              └─ pipeline type  : TRIGGERED (수동 sync 호출)
# MAGIC ```
# MAGIC
# MAGIC **실행 전 체크리스트:**
# MAGIC - [ ] 01_ingestion.py 완료 → `shtest.ragtest.chunks` 에 청크 저장됨
# MAGIC - [ ] Change Data Feed 활성화 확인 (01_ingestion 셀 8에서 확인)
# MAGIC - [ ] `embedding-bge-m3` Serving Endpoint가 Databricks에 배포된 상태

# COMMAND ----------
# MAGIC %md ## 셀 1: 의존성 확인

# COMMAND ----------

# databricks-sdk는 클러스터 라이브러리로 이미 설치됨 → %pip install 불필요
# databricks-vectorsearch 패키지는 namespace 충돌 문제로 사용하지 않음
# 대신 databricks-sdk의 w.vector_search_endpoints / w.vector_search_indexes API 사용
print("databricks-sdk (클러스터 라이브러리) 사용 — 추가 설치 불필요")

# COMMAND ----------
# MAGIC %md ## 셀 2: PROJECT_ROOT 설정

# COMMAND ----------

import sys
import os
from pathlib import Path

# 노트북 경로로 프로젝트 루트 자동 감지
try:
    _nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    PROJECT_ROOT = "/Workspace" + "/".join(_nb_path.split("/")[:-2])
except Exception:
    PROJECT_ROOT = "/Workspace/Repos/shseo@in4ucloud.com/ADBRAGTEST"

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.chdir(PROJECT_ROOT)

print(f"프로젝트 루트: {PROJECT_ROOT}")
print(f"Python 경로: {sys.path[:3]}")

# COMMAND ----------
# MAGIC %md ## 셀 3: 상수 정의

# COMMAND ----------

from src.utils.logger import get_logger

logger = get_logger("02_embedding")

# ── Unity Catalog ──────────────────────────────────────────────
CHUNKS_TABLE = "shtest.ragtest.chunks"

# ── Vector Search ──────────────────────────────────────────────
ENDPOINT_NAME          = "shrag-vs-endpoint"
INDEX_NAME             = "shtest.ragtest.chunks_index"
EMBEDDING_MODEL_ENDPOINT = "embedding-bge-m3"
PIPELINE_TYPE          = "TRIGGERED"

print(f"Chunks Table  : {CHUNKS_TABLE}")
print(f"VS Endpoint   : {ENDPOINT_NAME}")
print(f"VS Index      : {INDEX_NAME}")
print(f"Embedding 모델: {EMBEDDING_MODEL_ENDPOINT}")
print(f"Pipeline 타입 : {PIPELINE_TYPE}")

# COMMAND ----------
# MAGIC %md ## 셀 4: Chunks Table 사전 확인

# COMMAND ----------

df = spark.table(CHUNKS_TABLE)
total = df.count()

if total == 0:
    raise ValueError(
        f"{CHUNKS_TABLE}에 청크가 없습니다. "
        "01_ingestion.py를 먼저 실행하세요."
    )

print(f"총 청크 수: {total:,}개")
print()

print("문서별 청크 수:")
df.groupBy("doc_name", "doc_type", "parse_method").count() \
  .orderBy("doc_name") \
  .show(50, truncate=False)

# Change Data Feed 활성화 확인
props = spark.sql(f"DESCRIBE DETAIL {CHUNKS_TABLE}").collect()[0]["properties"]
cdf_enabled = props.get("delta.enableChangeDataFeed", "false")
print(f"Change Data Feed: {cdf_enabled}")

if cdf_enabled != "true":
    raise RuntimeError(
        "Change Data Feed가 비활성화 상태입니다. "
        "Delta Sync Index는 CDF가 필수입니다.\n"
        f"  ALTER TABLE {CHUNKS_TABLE} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"
    )

logger.info("사전 확인 완료: 총 %d개 청크, CDF=%s", total, cdf_enabled)

# COMMAND ----------
# MAGIC %md ## 셀 5: Vector Search Endpoint 생성 또는 확인

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import vectorsearch as vs_svc

w = WorkspaceClient()

def _ep_state(ep) -> str:
    """Endpoint 상태를 문자열로 반환."""
    state = ep.endpoint_status.state
    return state.value if hasattr(state, "value") else str(state)

# Endpoint 이미 존재하면 재사용
try:
    ep = w.vector_search_endpoints.get_endpoint(endpoint_name=ENDPOINT_NAME)
    state = _ep_state(ep)
    print(f"기존 엔드포인트 발견: {ENDPOINT_NAME} (상태: {state})")
    logger.info("기존 VS Endpoint 사용: %s (state=%s)", ENDPOINT_NAME, state)

except Exception:
    print(f"엔드포인트 생성 중: {ENDPOINT_NAME} ...")
    logger.info("VS Endpoint 생성 시작: %s", ENDPOINT_NAME)

    w.vector_search_endpoints.create_endpoint(
        name=ENDPOINT_NAME,
        endpoint_type=vs_svc.EndpointType.STANDARD,
    )

    # ONLINE 상태까지 대기 (최대 15분)
    max_wait_ep, poll_ep, elapsed_ep = 900, 30, 0
    while elapsed_ep < max_wait_ep:
        time.sleep(poll_ep)
        elapsed_ep += poll_ep
        ep = w.vector_search_endpoints.get_endpoint(endpoint_name=ENDPOINT_NAME)
        state = _ep_state(ep)
        print(f"  [{elapsed_ep:4d}s] Endpoint 상태: {state}")
        if "ONLINE" in state:
            break
        if "FAIL" in state or "OFFLINE" in state:
            raise RuntimeError(f"Endpoint 생성 실패: {state}")
    else:
        raise TimeoutError(f"Endpoint 생성 타임아웃 ({max_wait_ep}s)")

    print(f"엔드포인트 준비 완료: {ENDPOINT_NAME}")
    logger.info("VS Endpoint 생성 완료: %s", ENDPOINT_NAME)

# COMMAND ----------
# MAGIC %md ## 셀 6: Delta Sync Index 생성

# COMMAND ----------

def _idx_state(idx_obj) -> str:
    """Index 상태를 문자열로 반환."""
    status = idx_obj.status
    if status is None:
        return "UNKNOWN"
    state = getattr(status, "detailed_state", None) or getattr(status, "state", "UNKNOWN")
    return state.value if hasattr(state, "value") else str(state)

# Index 이미 존재하면 재사용
try:
    idx_obj = w.vector_search_indexes.get_index(index_name=INDEX_NAME)
    state = _idx_state(idx_obj)
    print(f"기존 인덱스 발견: {INDEX_NAME} (상태: {state})")
    logger.info("기존 VS Index 사용: %s (state=%s)", INDEX_NAME, state)

except Exception:
    print(f"인덱스 생성 중: {INDEX_NAME} ...")
    logger.info("VS Index 생성 시작: %s", INDEX_NAME)

    w.vector_search_indexes.create_index(
        name=INDEX_NAME,
        endpoint_name=ENDPOINT_NAME,
        primary_key="chunk_id",
        index_type=vs_svc.VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=vs_svc.DeltaSyncVectorIndexSpecRequest(
            source_table=CHUNKS_TABLE,
            pipeline_type=vs_svc.PipelineType.TRIGGERED,
            embedding_source_columns=[
                vs_svc.EmbeddingSourceColumn(
                    name="text",
                    embedding_model_endpoint_name=EMBEDDING_MODEL_ENDPOINT,
                )
            ],
        ),
    )
    print("인덱스 생성 요청 완료. 백그라운드 빌드 시작.")
    logger.info("VS Index 생성 요청 완료: %s", INDEX_NAME)

# COMMAND ----------
# MAGIC %md ## 셀 7: 인덱스 동기화 트리거 및 완료 대기

# COMMAND ----------

# TRIGGERED 파이프라인 — 명시적 sync 호출
print("동기화 트리거 중...")
w.vector_search_indexes.sync_index(index_name=INDEX_NAME)
logger.info("동기화 트리거 완료")
print("동기화 트리거 완료. 상태 모니터링 시작...\n")

_MAX_WAIT      = 1200
_POLL_INTERVAL = 30
_elapsed       = 0
_READY         = {"ONLINE", "ONLINE_NO_PENDING_UPDATE"}
_FAIL          = {"FAILED", "OFFLINE"}

while _elapsed < _MAX_WAIT:
    time.sleep(_POLL_INTERVAL)
    _elapsed += _POLL_INTERVAL

    idx_obj = w.vector_search_indexes.get_index(index_name=INDEX_NAME)
    state   = _idx_state(idx_obj)

    # indexed_row_count는 SDK 객체 속성 또는 as_dict()로 접근
    try:
        idx_dict   = idx_obj.as_dict()
        status_d   = idx_dict.get("status", {})
        indexed    = status_d.get("indexed_row_count", "?")
        total_src  = status_d.get("total_row_count", "?")
    except Exception:
        indexed = total_src = "?"

    print(f"[{_elapsed:5d}s] 상태: {state:<35} 인덱싱: {indexed}/{total_src}")
    logger.debug("VS Index 상태: state=%s, indexed=%s/%s", state, indexed, total_src)

    if state in _READY or any(r in state for r in _READY):
        print(f"\n인덱스 온라인 완료! 인덱싱된 청크: {indexed}개")
        logger.info("VS Index 온라인: %s, 청크 %s개", INDEX_NAME, indexed)
        break

    if state in _FAIL or any(f in state for f in _FAIL):
        logger.error("VS Index 빌드 실패: state=%s", state)
        raise RuntimeError(f"인덱스 빌드 실패 — 상태: {state}")

else:
    print(f"\n타임아웃 ({_MAX_WAIT}s). Databricks UI → Vector Search에서 상태 확인하세요.")
    logger.warning("VS Index 동기화 타임아웃: elapsed=%ds", _elapsed)

# COMMAND ----------
# MAGIC %md ## 셀 8: 검색 테스트

# COMMAND ----------

_TEST_QUERIES = [
    "GMP 준수 절차",
    "원료 수입 기준 및 시험 방법",
    "이탈 조사 보고서 작성",
    "세척 밸리데이션 기준",
]

print("=" * 70)
print("검색 테스트 (top-3)")
print("=" * 70)

for query in _TEST_QUERIES:
    print(f"\n▶ 쿼리: '{query}'")
    try:
        resp = w.vector_search_indexes.query_index(
            index_name=INDEX_NAME,
            query_text=query,
            columns=["chunk_id", "doc_name", "doc_type", "text"],
            num_results=3,
        )
        hits = resp.result.data_array or []

        if not hits:
            print("  결과 없음")
            continue

        for rank, row in enumerate(hits, 1):
            doc_name     = row[1] if len(row) > 1 else "?"
            doc_type     = row[2] if len(row) > 2 else "?"
            text_preview = (str(row[3])[:120] + "...") if len(row) > 3 else "?"
            score        = row[4] if len(row) > 4 else "?"
            print(f"  [{rank}] [{doc_type}] {doc_name}")
            print(f"      점수: {score:.4f}" if isinstance(score, float) else f"      점수: {score}")
            print(f"      {text_preview}")

    except Exception as e:
        logger.error("검색 테스트 실패: query='%s', error=%s", query, e)
        print(f"  검색 실패: {e}")

print("\n" + "=" * 70)

# COMMAND ----------
# MAGIC %md ## 완료

# COMMAND ----------

print("=" * 60)
print("Vector Search 인덱스 구성 완료!")
print("=" * 60)
print()
print("▶ 로컬 .env 파일에 아래 값을 입력하세요:")
print()
print(f"  DATABRICKS_VECTOR_SEARCH_ENDPOINT={ENDPOINT_NAME}")
print(f"  DATABRICKS_VECTOR_INDEX_NAME={INDEX_NAME}")
print()
print("▶ 다음 단계:")
print("  notebooks/03_rag_pipeline.py — 검색 + 생성 파이프라인 구축")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 완료
# MAGIC
# MAGIC Vector Search 인덱스 구성이 완료되었습니다.
# MAGIC
# MAGIC `.env` 업데이트 후 다음 단계:
# MAGIC **notebooks/03_rag_pipeline.py** — Retrieval + Generation 파이프라인 구축
