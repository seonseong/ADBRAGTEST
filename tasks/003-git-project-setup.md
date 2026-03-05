# Task 003: Git 저장소 초기화 및 프로젝트 구조 생성

## 개요

Git 저장소 초기화, 전체 프로젝트 디렉토리 골격 생성, YAML 설정 파일,
logger/config_loader 유틸 모듈 구현. 이후 모든 Task의 코드 기반이 되는 단계.

## 관련 파일

- `config/llm_config.yaml` - LLM 파라미터
- `config/chunking_config.yaml` - 청킹 파라미터
- `config/retrieval_config.yaml` - 검색 파라미터
- `config/prompt_templates.yaml` - 프롬프트 템플릿 (한국어 강제)
- `src/utils/logger.py` - 콘솔(INFO) + 파일(DEBUG) 로거
- `src/utils/config_loader.py` - Pydantic v2 기반 YAML 로더
- `README.md` - 프로젝트 문서

## 수락 기준

- [ ] `git log --oneline` 에서 initial commit 확인
- [ ] `src/`, `tests/`, `config/`, `notebooks/` 디렉토리 존재
- [ ] `uv run python -c "from src.utils.config_loader import load_llm_config; print(load_llm_config())"` 정상 출력
- [ ] `uv run python -c "from src.utils.logger import get_logger; get_logger('test').info('ok')"` 콘솔 + logs/app.log 동시 출력
- [ ] `just check` (lint + typecheck) 오류 없이 통과

## 구현 단계

- [x] Step 1: tasks/003-git-project-setup.md 작업 명세서 생성
- [x] Step 2: Git 저장소 초기화 (git init)
- [x] Step 3: 프로젝트 디렉토리 골격 생성 (src/, tests/, config/, notebooks/)
- [x] Step 4: README.md 작성
- [x] Step 5: config/*.yaml 4개 작성
- [x] Step 6: src/utils/logger.py 구현
- [x] Step 7: src/utils/config_loader.py 구현
- [x] Step 8: .gitignore에 logs/ 추가
- [ ] Step 9: just install-hooks + just check 검증 (사용자 실행)
- [ ] Step 10: git add + initial commit (사용자 확인 후 실행)
