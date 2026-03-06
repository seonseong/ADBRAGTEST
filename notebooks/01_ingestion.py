# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # 01. PDF 수집 및 전처리 파이프라인
# MAGIC
# MAGIC 이 노트북은 Databricks Volume의 PDF를 파싱, 청킹, Delta Table 저장까지 수행합니다.
# MAGIC
# MAGIC **실행 전 체크리스트:**
# MAGIC - [ ] Databricks Volume에 PDF 14건 업로드 완료 (로컬에서 `uv run python -m src.ingestion.uploader` 실행)
# MAGIC - [ ] 클러스터 라이브러리에 pymupdf, langchain-text-splitters, pydantic 설치 확인
# MAGIC - [ ] 아래 셀에서 easyocr 설치 완료

# COMMAND ----------
# MAGIC %md ## 셀 1: 의존성 설치

# COMMAND ----------

# 노트북 세션 의존성 설치
# 클러스터 라이브러리와 별개로 노트북 환경에 명시적으로 설치
%pip install pymupdf langchain-text-splitters easyocr

# COMMAND ----------
# MAGIC %md ## 셀 2: 프로젝트 패키지 경로 설정

# COMMAND ----------

import sys
import os

# Workspace에서 실행할 경우 프로젝트 루트를 sys.path에 추가
# 로컬 개발 시 Databricks Repos를 사용하면 /Workspace/Repos/<user>/<repo-name> 경로 사용
# 아래 경로를 실제 Databricks Workspace 경로로 수정하세요
PROJECT_ROOT = "/Workspace/Repos/shseo@in4ucloud.com/ADBRAGTEST"

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# config/ 디렉토리 기준 경로 설정 (config_loader가 상대경로 사용)
os.chdir(PROJECT_ROOT)

print(f"프로젝트 루트: {PROJECT_ROOT}")
print(f"Python 경로: {sys.path[:3]}")

# COMMAND ----------
# MAGIC %md ## 셀 3: 설정 로드

# COMMAND ----------

from src.utils.logger import get_logger
from src.utils.config_loader import load_chunking_config

logger = get_logger("01_ingestion")

# 청킹 설정 확인
cfg = load_chunking_config()
logger.info("청킹 설정: chunk_size=%d, chunk_overlap=%d, strategy=%s",
            cfg.chunk_size, cfg.chunk_overlap, cfg.strategy)

# Volume 경로 및 Table 이름 설정
VOLUME_PATH = "/Volumes/shtest/ragtest/shrag"      # .env의 DATABRICKS_VOLUME_PATH
CHUNKS_TABLE = "shtest.ragtest.chunks"             # .env의 DATABRICKS_CHUNKS_TABLE

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
# MAGIC %md ## 셀 5: PDF 파싱 (PyMuPDF + EasyOCR 폴백)

# COMMAND ----------

from src.ingestion.parser import PDFParser, parse_all

parser = PDFParser(ocr_languages=["ko", "en"], min_text_chars=50)

logger.info("PDF 파싱 시작...")
parsed_docs = parse_all(VOLUME_PATH, parser=parser)

# 파싱 결과 요약
print(f"\n{'='*60}")
print(f"파싱 완료: {len(parsed_docs)}/{len(pdf_files)}개 문서")
print(f"{'='*60}")
for doc in sorted(parsed_docs, key=lambda d: d.doc_name):
    ocr_info = f" (OCR: {doc.ocr_page_count}페이지)" if doc.ocr_page_count > 0 else ""
    print(f"  [{doc.doc_type}] {doc.doc_name[:50]:<50} {doc.total_text_length:>8,}자{ocr_info}")

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

# 전체 청크 수 확인
df = spark.table(CHUNKS_TABLE)
print(f"총 청크 수: {df.count():,}")
print()

# 문서별 청크 분포
print("문서별 청크 수:")
df.groupBy("doc_name", "doc_type", "parse_method").count() \
  .orderBy("doc_name") \
  .show(50, truncate=False)

# COMMAND ----------

# OCR 적용 문서 확인
ocr_df = df.filter(df.parse_method == "easyocr")
ocr_count = ocr_df.count()
print(f"EasyOCR 적용 청크: {ocr_count}개")

if ocr_count > 0:
    print("\nOCR 청크 샘플:")
    ocr_df.select("doc_name", "page_number", "text").show(3, truncate=100)

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
