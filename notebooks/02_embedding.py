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

# databricks-sdk와 함께 설치해야 namespace 충돌 방지
# (클러스터 라이브러리의 databricks-sdk와 충돌 시 vector_search 서브모듈을 찾지 못함)
%pip install "databricks-vectorsearch>=0.8.0,<0.9" "databricks-sdk>=0.40.0,<0.41"

# COMMAND ----------
# MAGIC %md ## 셀 2: PROJECT_ROOT 설정

# COMMAND ----------

import sys
import os
from pathlib import Path

# 노트북 경로로 프로젝트 루트 자동 감지
try:
    _nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    # 예: /Repos/email/ADBRAGTEST/notebooks/02_embedding
    #  → /Workspace/Repos/email/ADBRAGTEST
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
# Endpoint 이름: Workspace 단위 공유 리소스 (이미 있으면 재사용)
ENDPOINT_NAME = "shrag-vs-endpoint"

# Index 이름: catalog.schema.index_name 형식
INDEX_NAME = "shtest.ragtest.chunks_index"

# 임베딩 모델: Databricks Managed Embedding (Foundation Model API)
EMBEDDING_MODEL_ENDPOINT = "embedding-bge-m3"

# 파이프라인 타입: TRIGGERED(수동 sync) vs CONTINUOUS(CDF 실시간)
# 문서 수 14건 → TRIGGERED 충분
PIPELINE_TYPE = "TRIGGERED"

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
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Endpoint 이미 존재하면 재사용
try:
    ep = vsc.get_endpoint(ENDPOINT_NAME)
    ep_state = ep.get("endpoint_status", {}).get("state", "UNKNOWN")
    print(f"기존 엔드포인트 발견: {ENDPOINT_NAME} (상태: {ep_state})")
    logger.info("기존 VS Endpoint 사용: %s (state=%s)", ENDPOINT_NAME, ep_state)
except Exception:
    print(f"엔드포인트 생성 중: {ENDPOINT_NAME} ...")
    logger.info("VS Endpoint 생성 시작: %s", ENDPOINT_NAME)
    vsc.create_endpoint(name=ENDPOINT_NAME, endpoint_type="STANDARD")

    # ONLINE 상태가 될 때까지 대기 (최대 15분)
    max_wait_ep = 900
    poll_ep = 30
    elapsed_ep = 0
    while elapsed_ep < max_wait_ep:
        time.sleep(poll_ep)
        elapsed_ep += poll_ep
        ep = vsc.get_endpoint(ENDPOINT_NAME)
        ep_state = ep.get("endpoint_status", {}).get("state", "UNKNOWN")
        print(f"  [{elapsed_ep:4d}s] Endpoint 상태: {ep_state}")
        if ep_state == "ONLINE":
            break
        if ep_state in ("FAILED", "OFFLINE"):
            raise RuntimeError(f"Endpoint 생성 실패: {ep}")
    else:
        raise TimeoutError(f"Endpoint 생성 타임아웃 ({max_wait_ep}s)")

    print(f"엔드포인트 준비 완료: {ENDPOINT_NAME}")
    logger.info("VS Endpoint 생성 완료: %s", ENDPOINT_NAME)

# COMMAND ----------
# MAGIC %md ## 셀 6: Delta Sync Index 생성

# COMMAND ----------

# Index 이미 존재하면 재사용
try:
    idx = vsc.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME)
    desc = idx.describe()
    idx_state = desc.get("status", {}).get("detailed_state", "UNKNOWN")
    print(f"기존 인덱스 발견: {INDEX_NAME} (상태: {idx_state})")
    logger.info("기존 VS Index 사용: %s (state=%s)", INDEX_NAME, idx_state)

except Exception:
    print(f"인덱스 생성 중: {INDEX_NAME} ...")
    logger.info("VS Index 생성 시작: %s", INDEX_NAME)

    idx = vsc.create_delta_sync_index(
        endpoint_name=ENDPOINT_NAME,
        source_table_name=CHUNKS_TABLE,
        index_name=INDEX_NAME,
        pipeline_type=PIPELINE_TYPE,
        primary_key="chunk_id",
        embedding_source_column="text",
        embedding_model_endpoint_name=EMBEDDING_MODEL_ENDPOINT,
    )
    print(f"인덱스 생성 요청 완료. 백그라운드 빌드 시작.")
    logger.info("VS Index 생성 요청 완료: %s", INDEX_NAME)

# COMMAND ----------
# MAGIC %md ## 셀 7: 인덱스 동기화 트리거 및 완료 대기

# COMMAND ----------

# TRIGGERED 파이프라인은 sync()로 명시적 동기화 호출
print("동기화 트리거 중...")
idx.sync()
logger.info("동기화 트리거 완료")
print("동기화 트리거 완료. 상태 모니터링 시작...\n")

# 완료까지 대기 (최대 20분: 임베딩 생성 포함)
_MAX_WAIT = 1200
_POLL_INTERVAL = 30
_elapsed = 0
_READY_STATES = {"ONLINE", "ONLINE_NO_PENDING_UPDATE"}
_FAIL_STATES = {"FAILED", "OFFLINE"}

while _elapsed < _MAX_WAIT:
    time.sleep(_POLL_INTERVAL)
    _elapsed += _POLL_INTERVAL

    desc = idx.describe()
    status = desc.get("status", {})
    state = status.get("detailed_state", status.get("state", "UNKNOWN"))
    indexed = status.get("indexed_row_count", "?")
    total_src = status.get("total_row_count", "?")

    print(f"[{_elapsed:5d}s] 상태: {state:<35} 인덱싱: {indexed}/{total_src}")
    logger.debug("VS Index 상태: state=%s, indexed=%s/%s", state, indexed, total_src)

    if state in _READY_STATES:
        print(f"\n✓ 인덱스 온라인 완료! 인덱싱된 청크: {indexed:,}개")
        logger.info("VS Index 온라인: %s, 청크 %s개", INDEX_NAME, indexed)
        break

    if state in _FAIL_STATES:
        logger.error("VS Index 빌드 실패: %s", status)
        raise RuntimeError(f"인덱스 빌드 실패 — 상태: {status}")

else:
    print(f"\n⚠ 타임아웃 ({_MAX_WAIT}s). 인덱싱이 백그라운드에서 계속 진행 중일 수 있습니다.")
    print("Databricks UI → Vector Search에서 상태를 직접 확인하세요.")
    logger.warning("VS Index 동기화 타임아웃: elapsed=%ds", _elapsed)

# COMMAND ----------
# MAGIC %md ## 셀 8: 검색 테스트

# COMMAND ----------

# SOP/QMS 도메인 테스트 쿼리
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
        results = idx.similarity_search(
            query_text=query,
            columns=["chunk_id", "doc_name", "doc_type", "text"],
            num_results=3,
        )
        hits = results.get("result", {}).get("data_array", [])

        if not hits:
            print("  결과 없음")
            continue

        for rank, row in enumerate(hits, 1):
            # columns 순서: chunk_id, doc_name, doc_type, text, score
            doc_name = row[1] if len(row) > 1 else "?"
            doc_type = row[2] if len(row) > 2 else "?"
            text_preview = (row[3][:120] + "...") if len(row) > 3 else "?"
            score = row[4] if len(row) > 4 else "?"
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
