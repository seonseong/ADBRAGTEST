# ADB-RAG-1 MVP PRD

## 핵심 정보

**목적**: 제약 SOP/QMS 문서(PDF 14건)에 대한 자연어 질의응답을 가능하게 하여, 문서 탐색 시간과 정보 접근 비용을 줄인다.
**사용자**: Azure Databricks 환경에서 제약 품질관리(SOP/QMS) 문서를 다루는 개발자 및 데이터 엔지니어 (1인 개발)

---

## 사용자 여정

```
1. [환경 초기화]
   Databricks Workspace 접속 → Unity Catalog / Volume 구성 확인
   ↓

2. [문서 수집]
   files/ 폴더의 PDF 14건 → Databricks Volume 업로드
   ↓

3. [전처리 파이프라인]
   PDF 파싱 → 청킹 → 메타데이터 첨부 → Delta Table 저장
   ↓

4. [벡터 인덱스 구축]
   청크 데이터 → Foundation Model API 임베딩 생성
   → Delta Table에 벡터 컬럼 저장
   → Vector Search Managed Endpoint 동기화
   ↓

5. [RAG 파이프라인]
   사용자 질의 입력
   ↓ 질의 임베딩 생성
   → Vector Search 검색 (top_k 청크 반환)
   → (선택) Re-ranking
   → Prompt 조립 (template + context + 질의)
   → Foundation Model API 호출 → 응답 + 출처 반환
   ↓

6. [Gradio UI 확인]
   로컬에서 채팅 인터페이스로 질의응답 동작 검증
   ↓

7. [평가 및 개선]
   테스트 질의 세트 실행 → MLflow에 평가 지표 기록
   → 병목 식별 → 청킹/프롬프트/검색 파라미터 튜닝
   → 개선 전/후 지표 비교
```

---

## 기능 명세

### 1. MVP 핵심 기능

| ID | 기능명 | 설명 | MVP 필수 이유 | 관련 컴포넌트 |
|----|--------|------|-------------|--------------|
| **F001** | PDF 업로드 및 파싱 | files/ 폴더 PDF 14건을 Databricks Volume에 업로드하고, PyMuPDF 등으로 텍스트 추출 | 모든 RAG의 데이터 원천, 한글 문서 파싱 품질이 전체 품질을 결정 | uploader.py, parser.py |
| **F002** | 청킹 및 Delta Table 저장 | 추출된 텍스트를 chunk_size/chunk_overlap 기반으로 분할, 메타데이터(문서명, 페이지 번호, 문서 유형) 첨부 후 Delta Table에 저장 | 검색 품질의 기반 단위이며, 재실험 시 재처리 비용을 줄이기 위해 영속 저장 필수 | chunker.py, Delta Table |
| **F003** | 임베딩 생성 및 벡터 인덱스 구축 | Foundation Model API로 청크 임베딩 생성, Delta Table에 벡터 컬럼 저장, Vector Search Managed Endpoint 동기화 | 의미 기반 검색의 핵심 인프라 | embedder.py, Vector Search |
| **F004** | 벡터 검색(Retrieval) | 질의 임베딩으로 Vector Search에서 top_k 청크 검색, 중복 제거 및 점수 기반 정렬 | RAG의 R(Retrieval) 단계, 검색 품질이 응답 품질을 상한 결정 | searcher.py |
| **F005** | 응답 생성(Generation) | Prompt Template에 검색 컨텍스트와 질의를 조합하여 Foundation Model API 호출, 응답 텍스트와 출처 청크 반환 | RAG의 G(Generation) 단계, 최종 사용자 가치 전달 | generator.py, prompt_templates.yaml |
| **F006** | End-to-End 파이프라인 통합 | Ingestion -> Retrieval -> Generation 단계를 단일 인터페이스로 오케스트레이션, 각 단계별 소요 시간 로깅 | 개별 모듈의 통합 동작 보장 및 성능 측정 기반 | rag_pipeline.py |
| **F007** | RAG 평가 체계 | Faithfulness, Relevance, Answer Correctness 지표 자동 계산, MLflow에 실험 결과 기록 | 평가 없는 RAG는 미완성, 개선 방향 결정의 객관적 근거 | evaluator.py, MLflow |

### 2. MVP 필수 지원 기능

| ID | 기능명 | 설명 | MVP 필수 이유 | 관련 컴포넌트 |
|----|--------|------|-------------|--------------|
| **F010** | 설정 외부화 | llm_config, chunking_config, retrieval_config, prompt_templates를 YAML로 관리, 코드 변경 없이 파라미터 튜닝 가능 | 실험 반복 비용 최소화, 코드-설정 분리 원칙 | config/*.yaml, config_loader.py |
| **F011** | 구조화 로깅 | 각 파이프라인 단계의 입출력, 소요 시간, 에러를 일관된 형식으로 기록 | 문제 추적 및 성능 병목 식별의 필수 수단 | logger.py |
| **F012** | Re-ranking 모듈 | 벡터 검색 결과를 Cross-encoder 또는 규칙 기반으로 재정렬 | 검색 품질 향상의 선택적 레이어, 파이프라인에 교체 가능한 형태로 통합 | reranker.py |
| **F013** | Gradio 채팅 UI | 로컬에서 RAG 파이프라인을 채팅 형태로 동작 확인, 검색된 소스 문서 함께 표시 | 개발 중 빠른 동작 검증 수단 | app.py (Gradio) |
| **F014** | 개발환경 자동화 | justfile로 lint, format, typecheck, test, run-ui 명령 통합, pre-commit 훅으로 품질 자동 검사 | 1인 개발에서 반복 작업 실수 방지 및 일관성 유지 | justfile, .pre-commit-config.yaml |

### 3. MVP 이후 기능 (제외)

- 멀티 테넌트 / 접근 제어 (현재는 단일 개발자 환경)
- Databricks Job / Workflow 스케줄링 자동화
- Streaming 응답 (Gradio 로컬 확인 수준으로 충분)
- 문서 버전 관리 및 변경 감지 자동화
- 웹 배포 (Databricks Apps, Azure App Service 등)

---

## 컴포넌트 구조

```
ADB-RAG-1 컴포넌트 맵
├── [Phase 1] 환경 및 프로젝트 셋업
│   ├── Databricks Workspace / Unity Catalog / Volume 구성
│   ├── Python 개발환경 (uv, ruff, pyright)     - F014
│   └── Git 저장소 / 설정 파일 골격              - F010, F011, F014
│
├── [Phase 2] 데이터 수집 및 전처리
│   ├── uploader.py  PDF Volume 업로드           - F001
│   └── parser.py + chunker.py  파싱 / 청킹      - F001, F002
│
├── [Phase 3] 임베딩 및 벡터 인덱스
│   └── embedder.py + Vector Search 구성         - F003
│
├── [Phase 4] RAG 파이프라인
│   ├── searcher.py  벡터 검색                   - F004
│   ├── reranker.py  Re-ranking (선택)           - F012
│   ├── generator.py  응답 생성                  - F005
│   └── rag_pipeline.py  E2E 통합               - F006
│
├── [Phase 5] 프론트엔드 (로컬)
│   └── Gradio 채팅 UI                          - F013
│
└── [Phase 6] 평가 및 개선
    ├── evaluator.py + MLflow                    - F007
    └── 파라미터 튜닝 (YAML 수정)                - F010
```

---

## 컴포넌트별 상세 기능

### uploader.py + parser.py (PDF 수집 및 파싱)

> **구현 기능:** `F001` | **Phase:** 2 - 데이터 수집

| 항목 | 내용 |
|------|------|
| **역할** | files/ 폴더의 PDF 14건을 Databricks Volume에 업로드하고 텍스트를 추출하는 수집 파이프라인 진입점 |
| **실행 조건** | Unity Catalog Volume이 생성되어 있고, Databricks 접속 자격증명(.env)이 설정된 상태 |
| **처리 흐름** | files/*.pdf 열거 → Databricks Volume에 바이너리 업로드 → PyMuPDF로 페이지별 텍스트 추출 → 파싱 결과 반환 |
| **주요 기능** | - PDF 14건 일괄 업로드 (중복 스킵 로직 포함)<br>- 페이지별 텍스트 추출 (한글 인코딩, 테이블, 헤더/푸터 처리)<br>- 파싱 실패 문서 에러 로깅 및 계속 진행<br>- 파싱 품질 검증 로그 출력 (문서별 추출 텍스트 길이) |
| **출력** | 성공 → 문서별 파싱 결과 리스트 (문서명, 페이지 수, 텍스트), 실패 → 에러 로그 기록 후 계속 |

---

### chunker.py (청킹 및 Delta Table 저장)

> **구현 기능:** `F002` | **Phase:** 2 - 데이터 수집

| 항목 | 내용 |
|------|------|
| **역할** | 파싱된 텍스트를 검색 가능한 단위로 분할하고 메타데이터를 첨부하여 Delta Table에 영속 저장 |
| **실행 조건** | parser.py 실행 완료 후 파싱 결과가 존재, chunking_config.yaml 로드 완료 |
| **처리 흐름** | 파싱 텍스트 수신 → chunking_config 기반 분할 → 메타데이터 첨부 → Delta Table 스키마 생성 → 청크 저장 |
| **주요 기능** | - RecursiveCharacterTextSplitter 기반 청킹 (chunk_size, chunk_overlap YAML 관리)<br>- 메타데이터 첨부: doc_name, page_number, doc_type, chunk_index<br>- Delta Table 스키마 설계 및 Upsert (chunk_id 기준)<br>- 청킹 통계 로깅 (총 청크 수, 평균 길이, 문서별 분포) |
| **출력** | 성공 → Delta Table에 청크 데이터 저장 완료 로그, 실패 → 에러 상세 및 롤백 처리 |

---

### embedder.py (임베딩 생성 및 벡터 인덱스 구축)

> **구현 기능:** `F003` | **Phase:** 3 - 벡터 인덱스

| 항목 | 내용 |
|------|------|
| **역할** | Delta Table의 청크 텍스트를 Foundation Model API로 임베딩하고 Vector Search 인덱스를 동기화 |
| **실행 조건** | Delta Table에 청크 데이터 존재, Foundation Model API 접근 권한 확인, Vector Search Managed Endpoint 생성 완료 |
| **처리 흐름** | Delta Table 청크 조회 → 배치 단위 임베딩 API 호출 → Delta Table 벡터 컬럼 업데이트 → Vector Search 인덱스 동기화 트리거 |
| **주요 기능** | - Foundation Model API 배치 임베딩 (rate limit 대응 재시도 로직 포함)<br>- Delta Table embedding 컬럼 추가 및 저장<br>- Managed Vector Search Endpoint 생성 및 Delta Table 연동 설정<br>- 인덱스 동기화 완료 대기 및 샘플 검색 테스트 |
| **출력** | 성공 → Vector Search 인덱스 준비 완료, 실패 → API 에러/타임아웃 상세 로그 |

---

### searcher.py (벡터 검색)

> **구현 기능:** `F004` | **Phase:** 4 - RAG 파이프라인

| 항목 | 내용 |
|------|------|
| **역할** | 사용자 질의를 임베딩하여 Vector Search에서 관련 청크를 검색하고 후처리하는 Retrieval 모듈 |
| **실행 조건** | Vector Search 인덱스 동기화 완료, retrieval_config.yaml 로드 완료 |
| **처리 흐름** | 질의 수신 → 질의 임베딩 생성 → Vector Search 유사도 검색 → 중복 청크 제거 → 메타데이터 정렬 후 반환 |
| **주요 기능** | - 질의 임베딩 생성 (embedder 재사용)<br>- top_k, similarity_threshold 기반 검색 (YAML 관리)<br>- 검색 결과 중복 제거 (동일 문서 동일 페이지 중복 처리)<br>- 검색 품질 로깅 (검색 시간, 결과 수, 점수 분포) |
| **출력** | 성공 → 상위 k개 청크 리스트 (텍스트, 메타데이터, 유사도 점수), 빈 결과 → 빈 리스트 반환 및 경고 로그 |

---

### reranker.py (Re-ranking)

> **구현 기능:** `F012` | **Phase:** 4 - RAG 파이프라인 (선택)

| 항목 | 내용 |
|------|------|
| **역할** | 벡터 검색 결과를 추가 모델 또는 규칙 기반으로 재정렬하여 최종 컨텍스트 품질을 향상 |
| **실행 조건** | searcher.py 검색 결과 수신, retrieval_config.yaml의 reranker 설정 활성화 여부 확인 |
| **처리 흐름** | 검색 결과 수신 → reranker 활성화 여부 확인 → Cross-encoder 점수 계산 또는 규칙 적용 → 재정렬 결과 반환 |
| **주요 기능** | - 파이프라인에 교체 가능한 인터페이스로 통합 (활성화/비활성화 YAML 플래그)<br>- Cross-encoder 또는 규칙 기반 재정렬<br>- Re-ranking 전/후 순위 변화 로깅 |
| **출력** | 성공 → 재정렬된 청크 리스트, 비활성화 시 → 입력 그대로 패스스루 |

---

### generator.py (응답 생성)

> **구현 기능:** `F005` | **Phase:** 4 - RAG 파이프라인

| 항목 | 내용 |
|------|------|
| **역할** | 검색된 컨텍스트와 사용자 질의를 Prompt Template에 조합하여 Foundation Model API로 최종 답변을 생성 |
| **실행 조건** | 검색 결과(컨텍스트 청크) 수신, prompt_templates.yaml 및 llm_config.yaml 로드 완료 |
| **처리 흐름** | 컨텍스트 + 질의 수신 → system/user 프롬프트 템플릿 조합 → Foundation Model API 호출 → 응답 파싱 → 출처 메타데이터 첨부 |
| **주요 기능** | - 시스템/사용자 프롬프트 분리 템플릿 (prompt_templates.yaml 관리)<br>- temperature, max_tokens, 모델 버전 파라미터 (llm_config.yaml 관리)<br>- 응답 포맷팅 및 출처 청크 리스트 첨부<br>- API 에러 핸들링 (타임아웃, 토큰 초과, 속도 제한) |
| **출력** | 성공 → 응답 텍스트 + 출처 청크 리스트, 실패 → 에러 유형별 메시지 반환 |

---

### rag_pipeline.py (End-to-End 파이프라인)

> **구현 기능:** `F006` | **Phase:** 4 - RAG 파이프라인

| 항목 | 내용 |
|------|------|
| **역할** | Retrieval → (Re-ranking) → Generation 단계를 단일 인터페이스로 오케스트레이션하는 파이프라인 진입점 |
| **실행 조건** | searcher, reranker, generator 모듈 초기화 완료, 전체 설정 YAML 로드 완료 |
| **처리 흐름** | 질의 입력 → Retrieval 실행 → (Re-ranking 조건부 실행) → Generation 실행 → 응답 + 메타데이터 반환 |
| **주요 기능** | - 각 단계 모듈 의존성 주입 방식으로 조립<br>- 각 단계별 소요 시간 측정 및 전체 응답 시간 로깅<br>- 엣지 케이스 처리 (빈 검색 결과, 한글 특수문자, 긴 질의)<br>- 단위/통합 테스트 실행 진입점 제공 |
| **출력** | 성공 → 응답 텍스트 + 출처 + 단계별 소요 시간, 실패 → 단계명 명시 에러 메시지 |

---

### Gradio UI (로컬 확인용)

> **구현 기능:** `F013` | **Phase:** 5 - 프론트엔드

| 항목 | 내용 |
|------|------|
| **역할** | RAG 파이프라인의 동작을 채팅 인터페이스로 빠르게 검증하는 로컬 전용 UI |
| **실행 조건** | rag_pipeline.py 정상 동작 확인 완료, `just run-ui` 명령으로 로컬 실행 |
| **처리 흐름** | 질의 입력 → rag_pipeline 호출 → 응답 텍스트 + 출처 문서 목록 화면 표시 |
| **주요 기능** | - Gradio ChatInterface 기반 채팅 UI<br>- 응답 하단에 검색된 소스 문서명, 페이지 번호 표시<br>- justfile에 `just run-ui` 명령 등록 |
| **출력** | 성공 → 브라우저에서 채팅 인터페이스 확인, 실패 → 터미널 에러 로그 |

---

### evaluator.py (RAG 평가 및 개선)

> **구현 기능:** `F007` | **Phase:** 6 - 평가 및 개선

| 항목 | 내용 |
|------|------|
| **역할** | 테스트 질의 세트에 대한 RAG 응답 품질을 자동 평가하고 MLflow에 실험 결과를 기록 |
| **실행 조건** | rag_pipeline.py 통합 완료, 평가용 테스트 질의 세트(도메인 기반) 준비, MLflow 연동 설정 완료 |
| **처리 흐름** | 테스트 질의 세트 로드 → 각 질의에 대해 파이프라인 실행 → 평가 지표 계산 → MLflow 실험 기록 → 개선 방향 식별 |
| **주요 기능** | - 평가 지표 자동 계산 (Faithfulness, Relevance, Answer Correctness)<br>- 제약 SOP/QMS 도메인 기반 테스트 질의 세트 관리<br>- MLflow 실험 추적 (파라미터, 지표, 설정 파일 버전 기록)<br>- 개선 전/후 지표 비교 리포트 출력 |
| **출력** | 성공 → MLflow 실험 페이지에 지표 기록, 개선 식별 → YAML 파라미터 조정 후 재실험 |

---

### config/ (설정 외부화)

> **구현 기능:** `F010` | **전 Phase 공통**

| 항목 | 내용 |
|------|------|
| **역할** | 코드 변경 없이 파라미터 튜닝이 가능하도록 모든 가변 설정을 YAML 파일로 분리 관리 |
| **실행 조건** | 각 모듈 초기화 시 config_loader.py를 통해 자동 로드 |
| **관리 파일** | `llm_config.yaml`, `chunking_config.yaml`, `retrieval_config.yaml`, `prompt_templates.yaml` |
| **주요 기능** | - config_loader.py로 타입 안전한 YAML 로드 (Pydantic 검증)<br>- 환경변수(.env)와 YAML 설정의 역할 분리 (자격증명 vs 파라미터)<br>- 잘못된 설정값에 대한 명확한 ValidationError 출력 |
| **출력** | 성공 → 검증된 설정 객체 반환, 실패 → 누락 키 / 타입 불일치 에러 메시지 |

---

## 데이터 모델

### chunks (청크 Delta Table)

| 필드 | 설명 | 타입/관계 |
|------|------|----------|
| chunk_id | 청크 고유 식별자 (doc_name + page + index 해시) | STRING (PK) |
| doc_name | 원본 PDF 파일명 | STRING |
| doc_type | 문서 유형 (SOP, QMS 등) | STRING |
| page_number | 원본 페이지 번호 | INTEGER |
| chunk_index | 문서 내 청크 순번 | INTEGER |
| text | 청크 텍스트 원문 | STRING |
| embedding | 임베딩 벡터 | ARRAY[FLOAT] |
| created_at | 청크 생성 시각 | TIMESTAMP |

### evaluation_results (평가 결과)

| 필드 | 설명 | 타입/관계 |
|------|------|----------|
| eval_id | 평가 실행 고유 ID | STRING (PK) |
| mlflow_run_id | MLflow 실험 Run ID | STRING |
| question | 테스트 질의 원문 | STRING |
| faithfulness | Faithfulness 점수 (0~1) | FLOAT |
| relevance | Relevance 점수 (0~1) | FLOAT |
| answer_correctness | Answer Correctness 점수 (0~1) | FLOAT |
| config_snapshot | 평가 시점 YAML 설정 스냅샷 | JSON |
| evaluated_at | 평가 실행 시각 | TIMESTAMP |

---

## 기술 스택

### 언어 및 패키지 관리

| 기술 | 버전 | 용도 |
|------|------|------|
| Python | >= 3.13 | 전체 구현 언어 |
| uv | 최신 | 가상환경 및 의존성 관리 (의존성 버전 고정 필수, latest 사용 금지) |

### 코드 품질

| 기술 | 버전 | 용도 |
|------|------|------|
| ruff | 최신 | 린터 + 포매터 통합 |
| pyright | 최신 | 정적 타입 체커 (엄격 모드) |
| pre-commit | 최신 | 커밋 전 자동 품질 검사 (ruff, pyright) |
| just | 최신 | 작업 자동화 (lint, format, typecheck, test, run-ui) |

### Databricks 플랫폼

| 기술 | 버전 | 용도 |
|------|------|------|
| Databricks Foundation Model API | - | 임베딩 생성 + LLM 응답 생성 (DBRX, Llama 등) |
| Databricks Vector Search | Managed Endpoint | 벡터 유사도 검색 인덱스 |
| Databricks Unity Catalog | - | Delta Table, Volume, Schema 관리 |
| Databricks MLflow | 내장 | 실험 추적, 평가 지표 기록 |

### PDF 처리

| 기술 | 버전 | 용도 |
|------|------|------|
| PyMuPDF (fitz) | 최신 고정 | PDF 텍스트 추출 (한글 문서 대응) |
| langchain-text-splitters | 최신 고정 | RecursiveCharacterTextSplitter 청킹 |

### 설정 검증

| 기술 | 버전 | 용도 |
|------|------|------|
| pydantic | v2.x 고정 | YAML 설정 파일 타입 검증 |
| python-dotenv | 최신 고정 | .env 자격증명 로드 |

### 프론트엔드 (로컬 확인)

| 기술 | 버전 | 용도 |
|------|------|------|
| Gradio | 최신 고정 | 로컬 채팅 UI (배포 목적 아님) |

---

## 설정 파일 외부화 원칙

| 설정 파일 | 관리 항목 |
|-----------|-----------|
| `config/llm_config.yaml` | temperature, max_tokens, 모델 버전, 모델 엔드포인트 |
| `config/chunking_config.yaml` | chunk_size, chunk_overlap, 청킹 전략 |
| `config/retrieval_config.yaml` | top_k, similarity_threshold, 필터 조건, reranker 활성화 여부 |
| `config/prompt_templates.yaml` | system_prompt, user_prompt_template, few_shot_examples |

> 자격증명(Databricks Host, Token 등)은 `.env` 파일로만 관리하며, 절대 YAML이나 코드에 포함하지 않는다.

---

## 프로젝트 디렉토리 구조

```
ADB-RAG-1/
├── config/
│   ├── llm_config.yaml
│   ├── chunking_config.yaml
│   ├── retrieval_config.yaml
│   └── prompt_templates.yaml
├── src/
│   ├── ingestion/
│   │   ├── uploader.py          # Volume 업로드 모듈         (F001)
│   │   ├── parser.py            # PDF 파싱 모듈              (F001)
│   │   └── chunker.py           # 청킹 및 Delta Table 저장   (F002)
│   ├── embedding/
│   │   └── embedder.py          # 임베딩 생성 모듈           (F003)
│   ├── retrieval/
│   │   ├── searcher.py          # Vector Search 검색 모듈   (F004)
│   │   └── reranker.py          # Re-ranking 모듈           (F012)
│   ├── generation/
│   │   └── generator.py         # LLM 응답 생성 모듈        (F005)
│   ├── pipeline/
│   │   └── rag_pipeline.py      # E2E 파이프라인 오케스트레이션 (F006)
│   ├── evaluation/
│   │   └── evaluator.py         # RAG 평가 모듈             (F007)
│   └── utils/
│       ├── config_loader.py     # YAML 설정 로더 (Pydantic 검증) (F010)
│       └── logger.py            # 구조화 로깅 설정           (F011)
├── notebooks/                   # Databricks Notebook (탐색/실험용)
│   ├── 01_ingestion.py
│   ├── 02_embedding.py
│   ├── 03_retrieval_test.py
│   └── 04_evaluation.py
├── tests/
│   ├── test_parser.py
│   ├── test_chunker.py
│   └── test_pipeline.py
├── files/                       # 원본 PDF 문서 (14건)
├── tasks/                       # 작업 명세서 (Task 001 ~ 013)
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── justfile
├── pyproject.toml
├── ROADMAP.md
├── PRD.md
└── README.md
```

---

## 정합성 검증

### 기능 ID - 컴포넌트 매핑 확인

| 기능 ID | 기능명 | 구현 파일 | 페이지/컴포넌트 |
|---------|--------|-----------|--------------|
| F001 | PDF 업로드 및 파싱 | uploader.py, parser.py | PDF 수집 및 파싱 섹션 |
| F002 | 청킹 및 Delta Table 저장 | chunker.py | 청킹 및 Delta Table 저장 섹션 |
| F003 | 임베딩 생성 및 벡터 인덱스 | embedder.py | 임베딩 생성 및 벡터 인덱스 구축 섹션 |
| F004 | 벡터 검색 | searcher.py | 벡터 검색 섹션 |
| F005 | 응답 생성 | generator.py | 응답 생성 섹션 |
| F006 | E2E 파이프라인 통합 | rag_pipeline.py | E2E 파이프라인 섹션 |
| F007 | RAG 평가 체계 | evaluator.py | RAG 평가 및 개선 섹션 |
| F010 | 설정 외부화 | config/*.yaml, config_loader.py | 설정 외부화 섹션 |
| F011 | 구조화 로깅 | logger.py | 전 Phase 공통 |
| F012 | Re-ranking | reranker.py | Re-ranking 섹션 |
| F013 | Gradio 채팅 UI | app.py (Gradio) | Gradio UI 섹션 |
| F014 | 개발환경 자동화 | justfile, .pre-commit-config.yaml | Phase 1 환경 셋업 |
