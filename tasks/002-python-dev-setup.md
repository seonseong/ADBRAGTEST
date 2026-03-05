# Task 002: Python 개발환경 셋업

## 개요

uv 기반 Python 프로젝트 초기화 및 코드 품질 도구(ruff, pyright, pre-commit)와
작업 자동화(justfile)를 구성한다. 이후 모든 Task의 개발 기반이 되는 단계.

## 관련 파일

- `pyproject.toml` - 프로젝트 메타데이터, 의존성, ruff 설정
- `pyrightconfig.json` - 타입 체커 설정
- `.pre-commit-config.yaml` - 커밋 전 자동 품질 검사
- `justfile` - 작업 자동화 명령

## 수락 기준

- [ ] `uv sync` 실행 시 오류 없이 .venv 생성 및 의존성 설치 완료
- [ ] `just lint` 실행 시 오류 없이 완료
- [ ] `just format` 실행 시 오류 없이 완료
- [ ] `just typecheck` 실행 시 오류 없이 완료 (src/ 없으면 "0 errors" 허용)
- [ ] `just install-hooks` 실행 후 커밋 시 pre-commit 훅 자동 실행 확인

## 구현 단계

- [x] Step 1: tasks/002-python-dev-setup.md 작업 명세서 생성
- [x] Step 2: pyproject.toml 작성 (의존성 버전 고정, ruff 설정 포함)
- [x] Step 3: pyrightconfig.json 작성 (strict 모드)
- [x] Step 4: .pre-commit-config.yaml 작성 (ruff + pyright)
- [x] Step 5: justfile 작성 (lint/format/fix/typecheck/test/run-ui/install-hooks)
- [ ] Step 6: `uv sync` 실행하여 가상환경 및 의존성 설치 (사용자 실행)
- [ ] Step 7: `just install-hooks` 실행하여 pre-commit 훅 등록 (사용자 실행)
- [ ] Step 8: `just check` 실행하여 전체 품질 검사 통과 확인 (사용자 실행)

## 참고

- Python >= 3.13 필수 (uv가 자동으로 버전 관리)
- 의존성 버전 고정 원칙: `>=X.Y.Z,<X+1` 형식, latest 사용 금지
- .env 파일은 python-dotenv로 로드, 자격증명은 코드/YAML에 절대 하드코딩 금지
