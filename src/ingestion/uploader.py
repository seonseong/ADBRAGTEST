"""Databricks Volume PDF 업로드 모듈.

로컬 files/ 디렉토리의 PDF를 Databricks Volume에 업로드한다.
이미 존재하는 파일은 스킵하며, 실패한 파일은 로그 기록 후 계속 진행한다.

실행 방법:
    uv run python -m src.ingestion.uploader
"""

import os
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.files import UploadResponse
from dotenv import load_dotenv

from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

_FILES_DIR = Path("files")


def _build_volume_file_path(volume_path: str, filename: str) -> str:
    """Volume 내 파일 경로를 구성한다."""
    return f"{volume_path.rstrip('/')}/{filename}"


def upload_pdfs_to_volume(
    files_dir: Path,
    volume_path: str,
    overwrite: bool = False,
) -> dict[str, int]:
    """files/ 디렉토리의 PDF를 Databricks Volume에 업로드한다.

    Args:
        files_dir: 로컬 PDF 디렉토리 경로.
        volume_path: Databricks Volume 경로 (예: /Volumes/catalog/schema/volume).
        overwrite: True이면 이미 존재하는 파일도 덮어씀.

    Returns:
        통계 딕셔너리: {"success": N, "skipped": N, "failed": N}
    """
    client = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    pdf_files = sorted(files_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("files/ 디렉토리에 PDF 파일이 없습니다: %s", files_dir.resolve())
        return {"success": 0, "skipped": 0, "failed": 0}

    logger.info("업로드 시작: %d개 PDF 파일 → %s", len(pdf_files), volume_path)

    stats: dict[str, int] = {"success": 0, "skipped": 0, "failed": 0}

    for pdf_path in pdf_files:
        dest_path = _build_volume_file_path(volume_path, pdf_path.name)

        # 이미 존재하는 파일 스킵 (overwrite=False 시)
        if not overwrite:
            try:
                client.files.get_metadata(dest_path)
                logger.debug("스킵 (이미 존재): %s", pdf_path.name)
                stats["skipped"] += 1
                continue
            except Exception:
                pass  # 파일이 없으면 업로드 진행

        try:
            with pdf_path.open("rb") as f:
                _: UploadResponse = client.files.upload(dest_path, f, overwrite=overwrite)
            logger.info("업로드 완료: %s", pdf_path.name)
            stats["success"] += 1
        except Exception as e:
            logger.error("업로드 실패: %s → %s", pdf_path.name, e)
            stats["failed"] += 1

    logger.info(
        "업로드 완료 — 성공: %d개, 스킵: %d개, 실패: %d개",
        stats["success"],
        stats["skipped"],
        stats["failed"],
    )
    return stats


if __name__ == "__main__":
    volume_path = os.environ["DATABRICKS_VOLUME_PATH"]
    upload_pdfs_to_volume(_FILES_DIR, volume_path)
