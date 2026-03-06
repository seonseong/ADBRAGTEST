# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # 01. PDF 수집 및 전처리 파이프라인
# MAGIC
# MAGIC 이 노트북은 Databricks Volume의 PDF를 파싱, 청킹, Delta Table 저장까지 수행합니다.
# MAGIC
# MAGIC **실행 전 체크리스트:**
# MAGIC - [ ] Databricks Volume에 PDF 14건 업로드 완료 (로컬에서 `uv run python -m src.ingestion.uploader` 실행)
# MAGIC - [ ] 셀 1 실행 후 커널 재시작 확인, 셀 2부터 순서대로 실행

# COMMAND ----------
# MAGIC %md ## 셀 1: 의존성 설치

# COMMAND ----------

# PyMuPDF 설치 (PDF 텍스트 추출)
# EasyOCR 제외: Databricks 클러스터에서 cv2 SIGABRT 크래시 발생
# → 스캔 PDF 페이지는 PyMuPDF 결과를 그대로 사용 (텍스트 없으면 빈 청크로 건너뜀)
%pip install pymupdf

# COMMAND ----------
# MAGIC %md ## 셀 2: 프로젝트 패키지 경로 설정

# COMMAND ----------

import sys
import os
from pathlib import Path

# 현재 노트북 경로로 프로젝트 루트 자동 감지 (Repos/Users 경로 모두 지원)
try:
    _nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    # 예: /Repos/email/ADBRAGTEST/notebooks/01_ingestion
    #  → /Workspace/Repos/email/ADBRAGTEST
    PROJECT_ROOT = "/Workspace" + "/".join(_nb_path.split("/")[:-2])
except Exception:
    # dbutils 미사용 환경 폴백
    PROJECT_ROOT = "/Workspace/Repos/shseo@in4ucloud.com/ADBRAGTEST"

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.chdir(PROJECT_ROOT)

print(f"프로젝트 루트: {PROJECT_ROOT}")
print(f"Python 경로: {sys.path[:3]}")

# COMMAND ----------
# MAGIC %md ## 셀 3: 설정 로드

# COMMAND ----------

from src.utils.logger import get_logger
from src.utils.config_loader import load_chunking_config

logger = get_logger("01_ingestion")

cfg = load_chunking_config()
logger.info("청킹 설정: chunk_size=%d, chunk_overlap=%d, strategy=%s",
            cfg.chunk_size, cfg.chunk_overlap, cfg.strategy)

VOLUME_PATH = "/Volumes/shtest/ragtest/shrag"
CHUNKS_TABLE = "shtest.ragtest.chunks"

print(f"Volume 경로: {VOLUME_PATH}")
print(f"Delta Table: {CHUNKS_TABLE}")

# COMMAND ----------
# MAGIC %md ## 셀 4: Volume 내 PDF 목록 확인

# COMMAND ----------

import os
from pathlib import Path

pdf_files = [f for f in os.listdir(VOLUME_PATH) if f.endswith(".pdf")]
print(f"Volume 내 PDF 파일 수: {len(pdf_files)}")
for f in sorted(pdf_files):
    size_kb = os.path.getsize(f"{VOLUME_PATH}/{f}") // 1024
    print(f"  {f} ({size_kb} KB)")

# COMMAND ----------
# MAGIC %md ## 셀 5: PDF 파싱 (PyMuPDF)

# COMMAND ----------

from src.ingestion.parser import PDFParser, parse_all

# min_text_chars=0: 모든 페이지를 PyMuPDF로만 처리 (EasyOCR 비활성화)
# EasyOCR은 Databricks 클러스터에서 cv2 SIGABRT 크래시 발생으로 사용 불가
parser = PDFParser(min_text_chars=0)

logger.info("PDF 파싱 시작...")
parsed_docs = parse_all(VOLUME_PATH, parser=parser)

print(f"\n{'='*60}")
print(f"파싱 완료: {len(parsed_docs)}/{len(pdf_files)}개 문서")
print(f"{'='*60}")
for doc in sorted(parsed_docs, key=lambda d: d.doc_name):
    print(f"  [{doc.doc_type}] {doc.doc_name[:50]:<50} {doc.total_text_length:>8,}자")

# COMMAND ----------
# MAGIC %md ## 셀 6: 청킹 수행

# COMMAND ----------

from src.ingestion.chunker import DocumentChunker

chunker = DocumentChunker()
all_chunks = chunker.chunk_all(parsed_docs)

print(f"\n총 청크 수: {len(all_chunks):,}개")
print(f"평균 청크 길이: {sum(len(c.text) for c in all_chunks) / max(len(all_chunks), 1):.0f}자")

# COMMAND ----------
# MAGIC %md ## 셀 7: Delta Table 저장

# COMMAND ----------

saved_count = chunker.save_to_delta(spark, all_chunks, CHUNKS_TABLE)
print(f"\nDelta Table 저장 완료: {saved_count:,}개 청크")

# COMMAND ----------
# MAGIC %md ## 셀 8: 저장 결과 검증

# COMMAND ----------

df = spark.table(CHUNKS_TABLE)
print(f"총 청크 수: {df.count():,}")
print()

print("문서별 청크 수:")
df.groupBy("doc_name", "doc_type", "parse_method").count() \
  .orderBy("doc_name") \
  .show(50, truncate=False)

# COMMAND ----------

# Change Data Feed 활성화 확인 (Vector Search 연동 필수)
cdf_props = spark.sql(f"DESCRIBE DETAIL {CHUNKS_TABLE}").collect()[0]
print(f"Change Data Feed 활성화: {cdf_props['properties']}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 완료
# MAGIC
# MAGIC Delta Table 저장이 완료되었습니다.
# MAGIC 다음 단계: **notebooks/02_embedding.py** — 임베딩 생성 및 Vector Search 인덱스 구축
