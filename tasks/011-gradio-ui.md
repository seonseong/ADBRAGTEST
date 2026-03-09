# Task 011: Gradio 채팅 UI 구현

## 개요

RAG 파이프라인을 사용자가 직접 테스트할 수 있는 Gradio 5.x 기반 채팅 인터페이스를 구현한다.

## 관련 파일

| 파일 | 역할 |
|------|------|
| `app.py` | Gradio UI 진입점 (생성) |
| `src/pipeline/rag.py` | RAGPipeline — import 대상 |
| `src/utils/logger.py` | 로깅 — import 대상 |
| `config/retrieval_config.yaml` | 검색 파라미터 |
| `config/llm_config.yaml` | LLM 파라미터 |
| `justfile` | `run-ui: python app.py` |

## 수락 기준

- [ ] `just run-ui` 실행 시 http://localhost:7860 에서 UI 접속 가능
- [ ] 질문 입력 후 전송 시 "🔍 문서를 검색하고 있습니다..." 즉시 표시
- [ ] RAG 답변과 참조 출처(문서명, 페이지, score, 미리보기)가 함께 표시됨
- [ ] 대화 초기화 버튼이 채팅 히스토리와 출처 패널을 모두 초기화함
- [ ] 빈 입력 전송 시 오류 없이 처리됨
- [ ] Databricks 연결 실패 시 사용자 친화적 에러 메시지 표시

## 구현 단계

- [x] Step 1: `app.py` 생성 (Gradio 5.x gr.Blocks 레이아웃)
- [x] Step 2: RAGPipeline 싱글턴 초기화 로직 구현
- [x] Step 3: 참조 출처 HTML 카드 렌더링 구현
- [x] Step 4: Generator 기반 이벤트 핸들러 구현 (중간 상태 표시)
- [x] Step 5: 이벤트 연결 및 gr.State 히스토리 관리

## 실행 방법

```bash
# 의존성 동기화 (최초 1회)
uv sync

# UI 실행
just run-ui
```

브라우저: http://localhost:7860

## 환경변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `DATABRICKS_HOST` | — | Databricks 워크스페이스 URL (필수) |
| `DATABRICKS_TOKEN` | — | 개인 액세스 토큰 (필수) |
| `DATABRICKS_VECTOR_SEARCH_ENDPOINT` | `shrag-vs-endpoint` | VS Endpoint 이름 |
| `DATABRICKS_VECTOR_INDEX_NAME` | `shtest.ragtest.chunks_index` | VS Index 전체 경로 |
| `DATABRICKS_LLM_ENDPOINT` | `databricks-claude-sonnet` | LLM Serving Endpoint (이름 또는 URL) |

> `DATABRICKS_LLM_ENDPOINT`에 full URL이 저장된 경우 자동으로 이름만 추출함.
