# Task 004: PDF 문서 업로드 및 파싱 파이프라인 구현

## 개요

files/ 폴더의 PDF 14건을 Databricks Volume에 업로드하고,
PyMuPDF로 텍스트를 추출한다. 스캔/자필 PDF는 EasyOCR로 자동 폴백하여
한국어 품질을 최대한 확보한다.

## 관련 파일

- `src/ingestion/uploader.py` - 로컬 실행, SDK로 Volume 업로드
- `src/ingestion/parser.py` - Databricks에서 import, PyMuPDF + EasyOCR 폴백

## 수락 기준

- [ ] `uv run python -m src.ingestion.uploader` 실행 시 PDF 14건 Volume 업로드 완료
- [ ] Volume 경로에서 PDF 파일 존재 확인 (Databricks UI 또는 SDK)
- [ ] 노트북에서 parser.py import 후 텍스트 PDF 파싱 정상 동작
- [ ] 스캔 PDF (QA-CHC-240808-02.pdf)에서 EasyOCR 폴백 동작 및 한국어 텍스트 추출 확인
- [ ] 파싱 실패 문서는 에러 로그 후 계속 진행 (전체 중단 없음)

## PDF 파일 목록 및 처리 방식

| 파일명 | 유형 | 처리 방식 |
|--------|------|----------|
| DPD-SOP-0003 문서관리.pdf | 디지털 | PyMuPDF |
| DPD-SOP-0005 일탈관리.pdf | 디지털 | PyMuPDF |
| DPD-WI-QC-0158 검체 채취 방법.pdf | 디지털 | PyMuPDF |
| DPE-SOP-0001 업무분장(04).pdf | 디지털 | PyMuPDF |
| DPE-SOP-0001 업무분장(05).pdf | 디지털 | PyMuPDF |
| DPE-SOP-0003 문서의 관리(006).pdf | 디지털 | PyMuPDF |
| DPE-SOP-0052 제품표준서관리.pdf | 디지털 | PyMuPDF |
| DPE-WI-QA-0007 SOP작성방법.pdf | 디지털 | PyMuPDF |
| DPE-WI-QA-0106 QMS 일탈관리.pdf | 디지털 | PyMuPDF |
| CC-240909-004 변경통지서.pdf | 디지털 | PyMuPDF |
| CC-241206-001 주원료 제조원 추가.pdf | 디지털 | PyMuPDF |
| CC-241008-03 제조지시 변경.pdf | 디지털 | PyMuPDF |
| QA-CHC-240808-02.pdf | **스캔** | EasyOCR 폴백 |
| CC-240719-001.pdf | **자필** | EasyOCR 폴백 |

## 구현 단계

- [x] Step 1: tasks/004-pdf-upload-parse.md 작업 명세서 생성
- [x] Step 2: src/ingestion/uploader.py 구현
- [x] Step 3: src/ingestion/parser.py 구현 (PyMuPDF + EasyOCR 폴백)
- [ ] Step 4: `uv run python -m src.ingestion.uploader` 실행하여 Volume 업로드 (사용자)
- [ ] Step 5: Databricks 노트북에서 parser.py 동작 검증 (사용자)
