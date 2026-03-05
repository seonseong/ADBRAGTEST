# 기본: 명령 목록 출력
default:
    @just --list

# ─────────────────────────────────────────
# 코드 품질
# ─────────────────────────────────────────

# 린트 검사
lint:
    ruff check src tests

# 코드 포맷
format:
    ruff format src tests

# 린트 자동 수정
fix:
    ruff check --fix src tests

# 타입 검사
typecheck:
    pyright

# 린트 + 타입 검사 통합
check: lint typecheck

# ─────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────

# 전체 테스트 실행
test:
    pytest tests/ -v

# 특정 테스트 파일 실행 (예: just test-file tests/test_parser.py)
test-file FILE:
    pytest {{ FILE }} -v

# ─────────────────────────────────────────
# 실행
# ─────────────────────────────────────────

# Gradio 채팅 UI 실행 (로컬 확인용)
run-ui:
    python app.py

# ─────────────────────────────────────────
# pre-commit
# ─────────────────────────────────────────

# pre-commit 훅 설치
install-hooks:
    pre-commit install

# 전체 파일에 대해 pre-commit 수동 실행
run-hooks:
    pre-commit run --all-files

# ─────────────────────────────────────────
# 의존성
# ─────────────────────────────────────────

# 의존성 설치 (가상환경 생성 포함)
sync:
    uv sync

# dev 의존성 포함 설치
sync-dev:
    uv sync --extra dev
