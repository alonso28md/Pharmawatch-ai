"""Load regulatory documents and split them into metadata-tagged chunks."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings

logger = logging.getLogger(__name__)

SECTION_HEADER_PATTERN = re.compile(
    r"^(Article \d+[^\n]*|Rule \d+\b[^\n]*|SECCIÓN \d+[^\n]*|ANNEX VIII[^\n]*|CHAPTER [IVX]+[^\n]*)",
    re.MULTILINE,
)

DOCUMENT_DISPLAY_NAMES = {
    "mdr_vigilance_articles.txt": "MDR 2017/745 (Articles 87-92, Vigilance)",
    "mdr_annex_classification_rules.txt": "MDR 2017/745 Annex VIII (Classification Rules)",
    "aemps_vigilancia_guia.txt": "AEMPS - Guía de vigilancia de productos sanitarios",
}


@dataclass
class RawDocument:
    """A single loaded regulatory source file."""

    source: str
    display_name: str
    text: str


def clean_text(text: str) -> str:
    """Normalize line endings and collapse excessive blank lines."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_documents(directory: Path | str) -> list[RawDocument]:
    """Read every `.txt` file in `directory` into a `RawDocument`."""
    directory = Path(directory)
    documents: list[RawDocument] = []
    for path in sorted(directory.glob("*.txt")):
        text = clean_text(path.read_text(encoding="utf-8"))
        display_name = DOCUMENT_DISPLAY_NAMES.get(path.name, path.stem)
        documents.append(RawDocument(source=path.name, display_name=display_name, text=text))
    logger.info("Loaded %d regulatory document(s) from %s", len(documents), directory)
    return documents


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (section_label, section_text) spans based on in-text headers."""
    matches = list(SECTION_HEADER_PATTERN.finditer(text))
    if not matches:
        return [("General", text)]

    spans: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            spans.append(("Header", preamble))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label = match.group(1).strip()
        spans.append((label, text[start:end].strip()))
    return spans


def chunk_documents(
    documents: list[RawDocument],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict]:
    """Split documents into chunks tagged with {source, section, chunk_id} metadata."""
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    chunks: list[dict] = []
    for document in documents:
        for section_label, section_text in _split_into_sections(document.text):
            pieces = splitter.split_text(section_text)
            for idx, piece in enumerate(pieces):
                chunks.append(
                    {
                        "id": f"{document.source}::{section_label}::{idx}",
                        "text": piece,
                        "metadata": {
                            "source": document.display_name,
                            "source_file": document.source,
                            "section": section_label,
                            "chunk_id": idx,
                        },
                    }
                )
    logger.info("Produced %d chunk(s) from %d document(s)", len(chunks), len(documents))
    return chunks
