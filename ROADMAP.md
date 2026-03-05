# ADB-RAG-1 개발 로드맵

Azure Databricks 내장 기능만을 활용한 제약 SOP/QMS 문서 기반 RAG 시스템 구축

## 개요

ADB-RAG-1은 제약 SOP/QMS 문서(PDF 14건)를 대상으로 한 RAG 시스템입니다.
모든 RAG 컴포넌트를 Databricks 플랫폼 내에서 구현하며, 다음 기능을 제공합니다:

- **문서 수집/전처리**: PDF 파싱, 청킹, Delta Table 저장
- **벡터 검색**: Databricks Foundation Model API 임베딩 + Vector Search
- **질의응답**: Databricks Foundation Model API 기반 RAG 파이프라인
- **평가 체계**: MLflow 기반 RAG 품질 평가 및 실험 추적

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python >= 3.13 |
| 패키지/가상환경 | uv |
| 린터/포매터 | ruff |
| 타입 체커 | pyright |
| 작업 자동화 | just (justfile) |
| 임베딩 모델 | Databricks Foundation Model API |
| 벡터 스토어 | Databricks Vector Search (Managed Endpoint) |
| 생성 모델 | Databricks Foundation Model API (DBRX, Llama 등) |
| 파일 저장 | Databricks Volume (Unity Catalog) |
| 실험 추적 | Databricks MLflow |
| 프론트엔드 | Gradio (로컬 확인용) |

## 개발 워크플로우

1. **작업 계획**
   - 기존 코드베이스를 학습하고 현재 상태를 파악
   - 새로운 작업을 포함하도록 `ROADMAP.md` 업데이트
   - 우선순위 작업은 마지막 완료된 작업 다음에 삽입

2. **작업 생성**
   - `/tasks` 디렉토리에 새 작업 파일 생성
   - 명명 형식: `XXX-description.md` (예: `001-databricks-setup.md`)
   - 고수준 명세서, 관련 파일, 수락 기준, 구현 단계 포함
   - 예시를 위해 `/tasks` 디렉토리의 마지막 완료된 작업 참조
   - 초기 상태의 샘플로 `000-sample.md` 참조

3. **작업 구현**
   - 작업 파일의 명세서를 따름
   - 기능과 기능성 구현
   - 각 단계 후 작업 파일 내 단계 진행 상황 업데이트
   - 각 단계 완료 후 중단하고 추가 지시를 기다림

4. **로드맵 업데이트**
   - 로드맵에서 완료된 작업을 완료로 표시

## 브랜치 전략

```
prod <- staging <- dev <- feature/*
                    ^
                 hotfix/*
```

- 브랜치 네이밍: `{item_id}/{type}/{description}`
  - 예: `TASK-001/feat/databricks-setup`
- 커밋 메시지: `{task_id}/{type}: {description}`
  - 예: `TASK-001/feat: Databricks 환경 초기 설정`
- 커밋 타입: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert

---

## 개발 단계

### Phase 1: 환경 구성 및 프로젝트 셋업

- **Task 001: Databricks Workspace 및 Unity Catalog 구성** - 우선순위
  - Databricks Workspace 접속 확인 및 클러스터 생성
  - Unity Catalog 설정 (Catalog, Schema 생성)
  - Databricks Volume 생성 (PDF 저장용)
  - Foundation Model API 접근 권한 확인
  - Vector Search Endpoint 생성 가능 여부 확인

- **Task 002: Python 개발환경 셋업**
  - uv를 사용한 가상환경 및 프로젝트 초기화
  - pyproject.toml 작성 (의존성 버전 고정, latest 사용 금지)
  - ruff 설정 (린터/포매터 규칙 정의)
  - pyright 설정 (타입 체크 엄격도 설정)
  - pre-commit 훅 설정 (ruff, pyright 자동 실행)
  - justfile 작성 (lint, format, typecheck, test 등 작업 자동화)

- **Task 003: Git 저장소 초기화 및 프로젝트 구조 생성**
  - Git 저장소 초기화 및 .gitignore 작성
  - .env.example 작성 (Databricks Host, Token 등 키 설명 포함)
  - 프로젝트 디렉토리 구조 생성
  - README.md 작성 (실행 방법, 환경변수 설명 포함)
  - LLM 파라미터 설정 YAML 파일 생성 (config/llm_config.yaml)
  - logging 설정 모듈 구현

### Phase 2: 데이터 수집 및 전처리 (Ingestion)

- **Task 004: PDF 문서 업로드 및 파싱 파이프라인 구현**
  - `files/` 폴더의 PDF 14건을 Databricks Volume에 업로드하는 스크립트 작성
  - PDF 파싱 모듈 구현 (PyMuPDF 또는 Databricks 내장 파서 활용)
  - 한글 문서 파싱 품질 검증 (인코딩, 테이블, 이미지 텍스트 처리)
  - 파싱 결과 로깅 및 에러 핸들링

- **Task 005: 청킹 전략 구현 및 Delta Table 저장**
  - 청킹 전략 설계 (chunk_size, chunk_overlap YAML 외부화)
  - 청킹 모듈 구현 (RecursiveCharacterTextSplitter 등)
  - 메타데이터 추출 및 청크에 첨부 (문서명, 페이지 번호, 문서 유형 등)
  - Delta Table 스키마 설계 및 청크 데이터 저장
  - 청킹 결과 통계 로깅 (총 청크 수, 평균 길이 등)

### Phase 3: 임베딩 및 벡터 인덱스 구축

- **Task 006: 임베딩 생성 및 Vector Search 인덱스 구축**
  - Databricks Foundation Model API를 사용한 임베딩 생성 모듈 구현
  - 임베딩 모델 선택 및 파라미터 설정 (YAML 외부화)
  - Delta Table에 임베딩 벡터 컬럼 추가 및 저장
  - Databricks Vector Search Managed Endpoint 생성
  - Delta Table과 Vector Index 동기화 설정
  - 인덱스 검색 테스트 (유사도 검색 정상 동작 확인)

### Phase 4: RAG 파이프라인 구현

- **Task 007: 검색(Retrieval) 모듈 구현**
  - Vector Search 기반 검색 모듈 구현
  - 검색 파라미터 설정 (top_k, similarity_threshold 등 YAML 외부화)
  - 검색 결과 후처리 (중복 제거, 메타데이터 정렬)
  - 검색 품질 로깅 (검색 시간, 결과 수, 점수 분포)

- **Task 008: Re-ranking 모듈 구현 (선택사항)**
  - Re-ranking 전략 설계 (Cross-encoder 또는 규칙 기반)
  - Re-ranking 모듈 구현 및 파이프라인 통합
  - Re-ranking 적용 전/후 검색 품질 비교

- **Task 009: Prompt Template 및 생성(Generation) 모듈 구현**
  - Prompt Template 작성 (YAML 외부화, 시스템/사용자 프롬프트 분리)
  - Databricks Foundation Model API 기반 생성 모듈 구현
  - 모델 파라미터 설정 (temperature, max_tokens, 모델 버전 등 YAML 외부화)
  - 응답 포맷팅 및 출처 표시 로직 구현
  - 에러 핸들링 (API 타임아웃, 토큰 초과 등)

- **Task 010: End-to-End 파이프라인 통합**
  - 전체 RAG 파이프라인 통합 (Ingestion -> Retrieval -> Generation)
  - 파이프라인 오케스트레이션 모듈 구현
  - End-to-End 통합 테스트 (질의 -> 검색 -> 응답 흐름 검증)
  - 성능 로깅 (전체 응답 시간, 각 단계별 소요 시간)
  - 엣지 케이스 테스트 (빈 검색 결과, 긴 질의, 한글 특수문자 등)

### Phase 5: 프론트엔드 (로컬 확인용)

- **Task 011: Gradio 채팅 UI 구현**
  - Gradio 기반 채팅 인터페이스 구현
  - RAG 파이프라인 연동 (질의 입력 -> 응답 출력)
  - 검색된 소스 문서 표시 기능
  - 로컬 실행 확인 및 사용성 검증
  - justfile에 실행 명령 추가 (`just run-ui`)

### Phase 6: 평가 및 개선

- **Task 012: RAG 평가 체계 구축**
  - 평가 지표 정의 (Faithfulness, Relevance, Answer Correctness)
  - 평가용 테스트 질의 세트 작성 (제약 SOP/QMS 도메인 기반)
  - 평가 모듈 구현 (자동 평가 스크립트)
  - Databricks MLflow 연동 (실험 추적, 메트릭 기록)

- **Task 013: 파이프라인 개선 및 최적화**
  - 평가 결과 분석 및 병목 구간 식별
  - 청킹 전략 튜닝 (크기, 오버랩 조정)
  - 프롬프트 엔지니어링 개선
  - 검색 파라미터 최적화 (top_k, similarity_threshold 조정)
  - 개선 전/후 평가 지표 비교 (MLflow 실험 추적)

---

## 프로젝트 디렉토리 구조 (목표)

```
ADB-RAG-1/
├── config/
│   ├── llm_config.yaml          # LLM 파라미터 (temperature, max_tokens, 모델 버전)
│   ├── chunking_config.yaml     # 청킹 파라미터 (chunk_size, chunk_overlap)
│   ├── retrieval_config.yaml    # 검색 파라미터 (top_k, similarity_threshold)
│   └── prompt_templates.yaml    # 프롬프트 템플릿 (시스템/사용자 프롬프트)
├── src/
│   ├── __init__.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── uploader.py          # Volume 업로드 모듈
│   │   ├── parser.py            # PDF 파싱 모듈
│   │   └── chunker.py           # 청킹 모듈
│   ├── embedding/
│   │   ├── __init__.py
│   │   └── embedder.py          # 임베딩 생성 모듈
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── searcher.py          # Vector Search 검색 모듈
│   │   └── reranker.py          # Re-ranking 모듈
│   ├── generation/
│   │   ├── __init__.py
│   │   └── generator.py         # LLM 응답 생성 모듈
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── rag_pipeline.py      # End-to-End 파이프라인 오케스트레이션
│   ├── evaluation/
│   │   ├── __init__.py
│   │   └── evaluator.py         # RAG 평가 모듈
│   └── utils/
│       ├── __init__.py
│       ├── config_loader.py     # YAML 설정 로더
│       └── logger.py            # 로깅 설정
├── notebooks/                   # Databricks Notebook (탐색/실험용)
│   ├── 01_ingestion.py
│   ├── 02_embedding.py
│   ├── 03_retrieval_test.py
│   └── 04_evaluation.py
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_chunker.py
│   └── test_pipeline.py
├── files/                       # 원본 PDF 문서 (14건)
├── tasks/                       # 작업 명세서
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── justfile
├── pyproject.toml
├── ROADMAP.md
└── README.md
```

## 설정 파일 외부화 원칙

모든 LLM 파라미터와 파이프라인 설정은 YAML 파일로 외부화하여 코드 변경 없이 튜닝 가능하도록 구성합니다:

| 설정 파일 | 관리 항목 |
|-----------|-----------|
| `llm_config.yaml` | temperature, max_tokens, 모델 버전, 모델 엔드포인트 |
| `chunking_config.yaml` | chunk_size, chunk_overlap, 청킹 전략 |
| `retrieval_config.yaml` | top_k, similarity_threshold, 필터 조건 |
| `prompt_templates.yaml` | system_prompt, user_prompt_template, few_shot_examples |
