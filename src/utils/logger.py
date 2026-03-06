"""로깅 설정 모듈.

콘솔(INFO)과 파일(DEBUG)에 동시 출력하는 로거를 제공한다.
각 모듈에서 get_logger(__name__)으로 호출하여 사용한다.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Databricks Repos는 쓰기가 제한될 수 있으므로 /tmp 경로를 우선 사용
_LOG_DIR = Path("/tmp/adb-rag-logs") if Path("/tmp").exists() else Path("logs")
_LOG_FILE = _LOG_DIR / "app.log"
_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 10MB × 최대 5개 파일 보관
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5

_initialized = False


def _initialize_root_logger() -> None:
    """루트 로거에 콘솔/파일 핸들러를 최초 1회 설정한다."""
    global _initialized
    if _initialized:
        return

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # 핸들러별로 레벨을 조절

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # 콘솔 핸들러: INFO 이상만 출력
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 파일 핸들러: DEBUG 이상 모두 기록 (RotatingFileHandler)
    _LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root.addHandler(console_handler)
    root.addHandler(file_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """지정한 이름의 로거 인스턴스를 반환한다.

    Args:
        name: 로거 이름. 일반적으로 __name__ 을 전달한다.

    Returns:
        설정이 완료된 Logger 인스턴스.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("파이프라인 시작")
        >>> logger.debug("상세 디버그 정보")
    """
    _initialize_root_logger()
    return logging.getLogger(name)
