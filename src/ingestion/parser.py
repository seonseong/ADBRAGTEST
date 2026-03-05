"""PDF 파싱 모듈.

PyMuPDF로 텍스트를 추출하고, 페이지당 추출 텍스트가 짧으면
EasyOCR로 자동 폴백하여 스캔/자필 문서도 처리한다.

Databricks 노트북에서 import하여 사용한다.
클러스터에 easyocr이 설치되어 있어야 한다: %pip install easyocr
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 이 값 미만이면 스캔/자필로 판단하여 OCR 폴백
_MIN_TEXT_CHARS_PER_PAGE = 50

# 파일명에서 문서 유형 추출용 패턴
_DOC_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"\bSOP\b", "SOP"),
    (r"\bWI\b", "WI"),
    (r"\bCC-\d{6}", "CC"),
    (r"\bQA-", "QA"),
]


@dataclass
class ParsedPage:
    """단일 PDF 페이지 파싱 결과."""

    page_number: int  # 1-indexed
    text: str
    parse_method: str  # "pymupdf" | "easyocr"


@dataclass
class ParsedDocument:
    """전체 PDF 문서 파싱 결과."""

    doc_name: str
    doc_type: str
    total_pages: int
    pages: list[ParsedPage] = field(default_factory=list)

    @property
    def total_text_length(self) -> int:
        return sum(len(p.text) for p in self.pages)

    @property
    def ocr_page_count(self) -> int:
        return sum(1 for p in self.pages if p.parse_method == "easyocr")


class PDFParser:
    """PDF 파서.

    PyMuPDF로 텍스트를 추출하고, 텍스트가 부족한 페이지는
    EasyOCR(한/영)로 폴백한다. EasyOCR 모델은 첫 호출 시 lazy 로딩.

    Args:
        ocr_languages: EasyOCR 인식 언어 목록. 기본값 한국어 + 영어.
        min_text_chars: 페이지당 최소 텍스트 길이. 미만이면 OCR 폴백.
    """

    def __init__(
        self,
        ocr_languages: list[str] | None = None,
        min_text_chars: int = _MIN_TEXT_CHARS_PER_PAGE,
    ) -> None:
        self._ocr_languages = ocr_languages or ["ko", "en"]
        self._min_text_chars = min_text_chars
        self._reader = None  # EasyOCR lazy init (모델 로딩이 느림)

    def _get_ocr_reader(self):  # type: ignore[return]
        """EasyOCR Reader를 lazy 초기화한다."""
        if self._reader is None:
            try:
                import easyocr  # noqa: PLC0415

                logger.info("EasyOCR 모델 로딩 중 (언어: %s)...", self._ocr_languages)
                self._reader = easyocr.Reader(self._ocr_languages, gpu=False)
                logger.info("EasyOCR 모델 로딩 완료")
            except ImportError:
                logger.error(
                    "easyocr 패키지가 설치되어 있지 않습니다. "
                    "노트북 첫 셀에서 '%%pip install easyocr'를 실행하세요."
                )
                raise
        return self._reader

    def _extract_doc_type(self, filename: str) -> str:
        """파일명 패턴으로 문서 유형을 추출한다."""
        for pattern, doc_type in _DOC_TYPE_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                return doc_type
        return "기타"

    def _parse_page_with_pymupdf(self, page: fitz.Page) -> str:
        """PyMuPDF로 페이지 텍스트를 추출한다."""
        return page.get_text("text")  # type: ignore[no-any-return]

    def _parse_page_with_easyocr(self, page: fitz.Page) -> str:
        """EasyOCR로 페이지 텍스트를 추출한다.

        PDF 페이지를 이미지로 렌더링 후 OCR을 수행한다.
        """
        import numpy as np  # noqa: PLC0415

        reader = self._get_ocr_reader()

        # 200 DPI로 렌더링 (OCR 품질과 속도 균형)
        pix = page.get_pixmap(dpi=200)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.h, pix.w, pix.n
        )

        results = reader.readtext(img_array, detail=0, paragraph=True)
        return "\n".join(results)

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        """PDF 파일을 파싱하여 ParsedDocument를 반환한다.

        Args:
            pdf_path: 파싱할 PDF 파일 경로.

        Returns:
            ParsedDocument 인스턴스.

        Raises:
            FileNotFoundError: PDF 파일이 존재하지 않을 때.
            RuntimeError: PDF 열기 실패 시.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            msg = f"PDF 파일을 찾을 수 없습니다: {pdf_path}"
            raise FileNotFoundError(msg)

        doc_name = pdf_path.stem
        doc_type = self._extract_doc_type(pdf_path.name)

        logger.info("파싱 시작: %s (유형: %s)", pdf_path.name, doc_type)

        try:
            pdf_doc = fitz.open(str(pdf_path))
        except Exception as e:
            msg = f"PDF 열기 실패: {pdf_path.name} → {e}"
            raise RuntimeError(msg) from e

        parsed_pages: list[ParsedPage] = []

        with pdf_doc:
            total_pages = pdf_doc.page_count
            for page_num in range(total_pages):
                page = pdf_doc[page_num]
                page_number = page_num + 1  # 1-indexed

                # 1차: PyMuPDF
                text = self._parse_page_with_pymupdf(page)

                if len(text.strip()) >= self._min_text_chars:
                    parse_method = "pymupdf"
                else:
                    # 2차: EasyOCR 폴백
                    logger.debug(
                        "OCR 폴백: %s 페이지 %d (PyMuPDF 추출 %d자)",
                        pdf_path.name,
                        page_number,
                        len(text.strip()),
                    )
                    try:
                        text = self._parse_page_with_easyocr(page)
                        parse_method = "easyocr"
                    except Exception as e:
                        logger.error(
                            "OCR 실패: %s 페이지 %d → %s",
                            pdf_path.name,
                            page_number,
                            e,
                        )
                        text = ""
                        parse_method = "easyocr_failed"

                parsed_pages.append(
                    ParsedPage(
                        page_number=page_number,
                        text=text.strip(),
                        parse_method=parse_method,
                    )
                )

        result = ParsedDocument(
            doc_name=doc_name,
            doc_type=doc_type,
            total_pages=total_pages,
            pages=parsed_pages,
        )

        logger.info(
            "파싱 완료: %s — %d페이지, 총 %d자, OCR 적용 %d페이지",
            pdf_path.name,
            result.total_pages,
            result.total_text_length,
            result.ocr_page_count,
        )

        return result


def parse_all(
    pdf_dir: str | Path,
    parser: PDFParser | None = None,
) -> list[ParsedDocument]:
    """디렉토리 내 모든 PDF를 파싱한다.

    Args:
        pdf_dir: PDF 파일이 있는 디렉토리 경로 (로컬 또는 Volume 마운트 경로).
        parser: 재사용할 PDFParser 인스턴스. None이면 기본값으로 생성.

    Returns:
        ParsedDocument 리스트. 실패한 파일은 로그 기록 후 건너뜀.
    """
    pdf_dir = Path(pdf_dir)
    if parser is None:
        parser = PDFParser()

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    logger.info("전체 파싱 시작: %d개 파일", len(pdf_files))

    results: list[ParsedDocument] = []
    for pdf_path in pdf_files:
        try:
            doc = parser.parse(pdf_path)
            results.append(doc)
        except Exception as e:
            logger.error("파싱 실패 (건너뜀): %s → %s", pdf_path.name, e)

    logger.info("전체 파싱 완료: %d/%d개 성공", len(results), len(pdf_files))
    return results
