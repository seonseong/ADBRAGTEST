"""Databricks 클러스터 라이브러리 설치 스크립트.

클러스터에 RAG 파이프라인에 필요한 PyPI 패키지를 설치하고
설치 완료(INSTALLED 상태)까지 대기한다.

실행 방법:
    uv run python -m src.utils.install_cluster_libs
"""

import os
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.compute import Library, PythonPyPiLibrary
from dotenv import load_dotenv

from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# 클러스터에 설치할 PyPI 패키지 목록
# easyocr는 용량(~300MB)이 커서 노트북 %pip으로 별도 설치
_LIBRARIES: list[str] = [
    "pymupdf>=1.25.0,<1.26",
    "langchain-text-splitters>=0.3.0,<0.4",
    "pydantic>=2.10.0,<3",
    "pyyaml>=6.0.0,<7",
    "python-dotenv>=1.0.0,<2",
]

_POLL_INTERVAL_SEC = 10
_MAX_WAIT_SEC = 600  # 10분


def _build_libraries(packages: list[str]) -> list[Library]:
    return [Library(pypi=PythonPyPiLibrary(package=pkg)) for pkg in packages]


def install_and_wait(cluster_id: str, packages: list[str]) -> None:
    """패키지를 클러스터에 설치하고 완료될 때까지 대기한다."""
    client = WorkspaceClient(
        host=os.environ["DATABRICKS_HOST"],
        token=os.environ["DATABRICKS_TOKEN"],
    )

    libraries = _build_libraries(packages)

    logger.info("라이브러리 설치 요청: 클러스터=%s, 패키지=%d개", cluster_id, len(packages))
    for pkg in packages:
        logger.info("  - %s", pkg)

    client.libraries.install(cluster_id=cluster_id, libraries=libraries)
    logger.info("설치 요청 전송 완료. 상태 모니터링 시작...")

    elapsed = 0
    while elapsed < _MAX_WAIT_SEC:
        time.sleep(_POLL_INTERVAL_SEC)
        elapsed += _POLL_INTERVAL_SEC

        statuses = client.libraries.cluster_status(cluster_id=cluster_id)
        # SDK 버전에 따라 ClusterLibraryStatuses 객체 또는 list 반환
        if isinstance(statuses, list):
            lib_statuses = statuses
        else:
            lib_statuses = list(statuses.library_statuses or [])

        # 설치 대상 패키지만 필터링 (패키지명 앞부분 비교)
        target_pkgs = {pkg.split(">=")[0].split(">")[0].split("==")[0] for pkg in packages}
        relevant = [
            s for s in lib_statuses
            if s.library
            and s.library.pypi
            and any(pkg.lower() in (s.library.pypi.package or "").lower() for pkg in target_pkgs)
        ]

        if not relevant:
            logger.debug("(%ds) 상태 정보 아직 없음...", elapsed)
            continue

        # 상태 출력
        all_done = True
        has_error = False
        for s in relevant:
            pkg_name = s.library.pypi.package if s.library and s.library.pypi else "?"
            status_str = s.status.value if s.status else "UNKNOWN"
            logger.info("  [%s] %s", status_str, pkg_name)

            if status_str not in ("INSTALLED",):
                all_done = False
            if status_str in ("FAILED", "UNINSTALL_ON_RESTART"):
                has_error = True
                logger.error("설치 실패: %s → %s", pkg_name, s.messages)

        if has_error:
            raise RuntimeError("일부 라이브러리 설치 실패. 위 로그를 확인하세요.")

        if all_done and len(relevant) == len(packages):
            logger.info("모든 라이브러리 설치 완료! (소요: %d초)", elapsed)
            return

    raise TimeoutError(f"라이브러리 설치가 {_MAX_WAIT_SEC}초 내에 완료되지 않았습니다.")


if __name__ == "__main__":
    cluster_id = os.environ["DATABRICKS_CLUSTER_ID"]
    install_and_wait(cluster_id, _LIBRARIES)
