"""청킹 및 Delta Table 저장 모듈.

파싱된 문서를 RecursiveCharacterTextSplitter로 청킹하고
메타데이터를 첨부하여 Delta Table에 Upsert한다.

Databricks 노트북(PySpark 환경)에서 import하여 사용한다.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.ingestion.parser import ParsedDocument
from src.utils.config_loader import load_chunking_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Delta Table DDL (Change Data Feed 활성화 포함)
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table_name} (
    chunk_id     STRING NOT NULL,
    doc_name     STRING NOT NULL,
    doc_type     STRING,
    page_number  INT,
    chunk_index  INT,
    text         STRING,
    parse_method STRING,
    created_at   TIMESTAMP
)
TBLPROPERTIES (delta.enableChangeDataFeed = true)
"""

_MERGE_SQL = """
MERGE INTO {table_name} AS target
USING (SELECT * FROM {temp_view}) AS source
ON target.chunk_id = source.chunk_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
"""


@dataclass
class Chunk:
    """단일 청크 데이터."""

    chunk_id: str
    doc_name: str
    doc_type: str
    page_number: int
    chunk_index: int
    text: str
    parse_method: str
    created_at: datetime


def _make_chunk_id(doc_name: str, page_number: int, chunk_index: int) -> str:
    """chunk_id를 sha256 해시로 생성한다 (재실행 시 동일 ID 보장)."""
    raw = f"{doc_name}::{page_number}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()


class DocumentChunker:
    """문서 청커.

    chunking_config.yaml의 파라미터로 RecursiveCharacterTextSplitter를 초기화하고,
    파싱된 문서를 청킹한 뒤 Delta Table에 Upsert한다.
    """

    def __init__(self) -> None:
        cfg = load_chunking_config()
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        logger.debug(
            "청커 초기화 완료: chunk_size=%d, chunk_overlap=%d",
            cfg.chunk_size,
            cfg.chunk_overlap,
        )

    def chunk_document(self, doc: ParsedDocument) -> list[Chunk]:
        """ParsedDocument를 청킹하여 Chunk 리스트를 반환한다.

        페이지 텍스트가 비어 있으면 해당 페이지는 건너뜀.
        """
        chunks: list[Chunk] = []
        created_at = datetime.now(tz=timezone.utc)

        for page in doc.pages:
            if not page.text.strip():
                logger.debug(
                    "빈 페이지 건너뜀: %s 페이지 %d",
                    doc.doc_name,
                    page.page_number,
                )
                continue

            texts = self._splitter.split_text(page.text)

            for idx, text in enumerate(texts):
                if not text.strip():
                    continue
                chunks.append(
                    Chunk(
                        chunk_id=_make_chunk_id(doc.doc_name, page.page_number, idx),
                        doc_name=doc.doc_name,
                        doc_type=doc.doc_type,
                        page_number=page.page_number,
                        chunk_index=idx,
                        text=text.strip(),
                        parse_method=page.parse_method,
                        created_at=created_at,
                    )
                )

        logger.debug(
            "청킹 완료: %s → %d개 청크 (평균 %.0f자)",
            doc.doc_name,
            len(chunks),
            sum(len(c.text) for c in chunks) / max(len(chunks), 1),
        )
        return chunks

    def chunk_all(self, docs: list[ParsedDocument]) -> list[Chunk]:
        """여러 문서를 청킹하고 통계를 로깅한다."""
        all_chunks: list[Chunk] = []
        for doc in docs:
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)

        doc_stats = {}
        for c in all_chunks:
            doc_stats[c.doc_name] = doc_stats.get(c.doc_name, 0) + 1

        logger.info("전체 청킹 완료: 총 %d개 청크, %d개 문서", len(all_chunks), len(doc_stats))
        for doc_name, count in sorted(doc_stats.items()):
            logger.info("  %-50s %d개", doc_name, count)

        return all_chunks

    def save_to_delta(self, spark: object, chunks: list[Chunk], table_name: str) -> int:  # type: ignore[type-arg]
        """Chunk 리스트를 Delta Table에 Upsert한다.

        Args:
            spark: SparkSession 인스턴스 (Databricks 환경에서 자동 제공).
            chunks: 저장할 Chunk 리스트.
            table_name: 저장 대상 Delta Table 이름 (catalog.schema.table 형식).

        Returns:
            저장된 청크 수.
        """
        from pyspark.sql import SparkSession  # noqa: PLC0415

        _spark: SparkSession = spark  # type: ignore[assignment]

        # Delta Table 생성 (없으면)
        _spark.sql(_CREATE_TABLE_SQL.format(table_name=table_name))
        logger.info("Delta Table 준비 완료: %s", table_name)

        # Chunk → Row 변환
        rows = [
            (
                c.chunk_id,
                c.doc_name,
                c.doc_type,
                c.page_number,
                c.chunk_index,
                c.text,
                c.parse_method,
                c.created_at,
            )
            for c in chunks
        ]

        schema = (
            "chunk_id STRING, doc_name STRING, doc_type STRING, "
            "page_number INT, chunk_index INT, text STRING, "
            "parse_method STRING, created_at TIMESTAMP"
        )

        df = _spark.createDataFrame(rows, schema=schema)
        temp_view = "_chunks_temp"
        df.createOrReplaceTempView(temp_view)

        # Upsert (chunk_id 기준)
        _spark.sql(_MERGE_SQL.format(table_name=table_name, temp_view=temp_view))

        saved_count = _spark.sql(f"SELECT COUNT(*) FROM {table_name}").collect()[0][0]
        logger.info("Delta Table 저장 완료: %s (총 %d개 청크)", table_name, saved_count)

        return int(saved_count)
