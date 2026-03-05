# Task 005: 청킹 전략 구현 및 Delta Table 저장

## 개요

파싱된 텍스트를 RecursiveCharacterTextSplitter로 청킹하고,
메타데이터(doc_name, page_number, doc_type 등)를 첨부하여
Delta Table(shtest.ragtest.chunks)에 저장한다.
Vector Search 동기화를 위해 Change Data Feed를 활성화한다.

## 관련 파일

- `src/ingestion/chunker.py` - 청킹 및 Delta Table 저장 모듈
- `notebooks/01_ingestion.py` - 전체 파이프라인 오케스트레이션

## 수락 기준

- [ ] `shtest.ragtest.chunks` Delta Table 생성 확인
- [ ] `delta.enableChangeDataFeed = true` 설정 확인
- [ ] 전체 청크 수 확인 (14개 PDF 기준, 예상 500~2000개)
- [ ] 각 청크에 doc_name, doc_type, page_number, chunk_index 메타데이터 포함 확인
- [ ] 동일 청크 재실행 시 upsert 동작 (중복 삽입 없음)
- [ ] 청킹 통계 로그 출력 (총 청크 수, 문서별 청크 수, 평균 텍스트 길이)

## Delta Table 스키마

```
chunk_id     STRING (PK, sha256 해시)
doc_name     STRING
doc_type     STRING (SOP/WI/CC/기타)
page_number  INT
chunk_index  INT
text         STRING
parse_method STRING (pymupdf/easyocr)
created_at   TIMESTAMP
```

## 구현 단계

- [x] Step 1: tasks/005-chunking-delta-table.md 작업 명세서 생성
- [x] Step 2: src/ingestion/chunker.py 구현
- [x] Step 3: notebooks/01_ingestion.py 작성
- [ ] Step 4: Databricks 노트북 실행 및 Delta Table 생성 확인 (사용자)
- [ ] Step 5: 청크 통계 확인 후 chunking_config.yaml 파라미터 조정 여부 결정 (사용자)
