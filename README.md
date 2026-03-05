# ADB-RAG-1

제약 SOP/QMS 문서(PDF 14건)에 대한 자연어 질의응답 RAG 시스템.
Azure Databricks 내장 기능(Foundation Model API, Vector Search, MLflow)만을 활용하여 구현.

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.13 |
| 패키지 관리 | uv |
| 린터/포매터 | ruff |
| 타입 체커 | pyright |
| 작업 자동화 | just |
| 임베딩 | Databricks Foundation Model API (BGE-M3) |
| 벡터 스토어 | Databricks Vector Search (Managed Endpoint) |
| 생성 모델 | Databricks Foundation Model API (Claude Sonnet) |
| 파일 저장 | Databricks Volume (Unity Catalog) |
| 실험 추적 | Databricks MLflow |
| 로컬 UI | Gradio |

---

## 사전 요구사항

```bash
# uv 설치
pip install uv

# just 설치 (Windows)
winget install Casey.Just
```

---

## 시작하기

### 1. 의존성 설치

```bash
uv sync --extra dev
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 실제 값 입력
```

필요한 환경변수 목록은 [.env.example](.env.example) 참조.

### 3. pre-commit 훅 설치

```bash
just install-hooks
```

### 4. 코드 품질 검사

```bash
just check       # lint + typecheck
just format      # 코드 포맷
just test        # 테스트 실행
```

### 5. Gradio UI 실행 (로컬 확인용)

```bash
just run-ui
```

---

## 주요 명령 (justfile)

| 명령 | 설명 |
|------|------|
| `just lint` | ruff 린트 검사 |
| `just format` | ruff 코드 포맷 |
| `just fix` | ruff 자동 수정 |
| `just typecheck` | pyright 타입 검사 |
| `just check` | lint + typecheck 통합 |
| `just test` | pytest 전체 실행 |
| `just run-ui` | Gradio UI 실행 |
| `just install-hooks` | pre-commit 훅 설치 |
| `just sync` | 의존성 설치 |

---

## 프로젝트 구조

```
ADB-RAG-1/
├── config/
│   ├── llm_config.yaml          # LLM 파라미터 (temperature, max_tokens)
│   ├── chunking_config.yaml     # 청킹 파라미터 (chunk_size, chunk_overlap)
│   ├── retrieval_config.yaml    # 검색 파라미터 (top_k, threshold)
│   └── prompt_templates.yaml    # 프롬프트 템플릿
├── src/
│   ├── ingestion/               # PDF 업로드 및 파싱
│   ├── embedding/               # 임베딩 생성
│   ├── retrieval/               # 벡터 검색
│   ├── generation/              # LLM 응답 생성
│   ├── pipeline/                # E2E 파이프라인
│   ├── evaluation/              # RAG 평가
│   └── utils/
│       ├── logger.py            # 로깅 설정
│       └── config_loader.py     # YAML 설정 로더
├── notebooks/                   # Databricks Notebook (탐색/실험용)
├── tests/                       # 테스트
├── files/                       # 원본 PDF 문서 (Git 제외)
├── tasks/                       # 작업 명세서
├── .env.example                 # 환경변수 예시
└── pyproject.toml
```

---

## 설정 파일 구조

모든 튜닝 파라미터는 `config/*.yaml`로 외부화. 코드 변경 없이 실험 가능.

| 파일 | 관리 항목 |
|------|----------|
| `llm_config.yaml` | temperature, max_tokens, model_label |
| `chunking_config.yaml` | chunk_size, chunk_overlap, strategy |
| `retrieval_config.yaml` | top_k, similarity_threshold, enable_reranker |
| `prompt_templates.yaml` | system_prompt, user_prompt_template |

> 자격증명(Databricks Host, Token, 엔드포인트 URL)은 `.env`로만 관리.
> 절대 YAML이나 코드에 포함하지 않는다.
