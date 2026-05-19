from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever


CARD_PATTERN = re.compile(r"(?=^### MED-\d{5,6}｜)", re.MULTILINE)
TITLE_PATTERN = re.compile(r"^### (?P<record_id>MED-\d{5,6})｜(?P<system>[^｜]+)｜(?P<disease>[^｜]+)｜(?P<scenario>.+)$")
KEYWORD_PATTERN = re.compile(r"\*\*RAG检索关键词\*\*\s*\n(?P<keywords>.+)")
COUNT_PATTERN = re.compile(r"本文件知识卡数量：(?P<count>\d+)")

BUILTIN_FILENAME = "builtin_medical_corpus_100000.md"
BUILTIN_USER_ID = "builtin_medical_corpus"
BUILTIN_DISPLAY_NAME = "内置医疗知识库｜常见疾病诊疗语料（100000条）"

SYMPTOM_TERMS = [
    "发热", "咳嗽", "咳痰", "鼻塞", "流涕", "咽痛", "喘息", "胸闷", "胸痛", "气短", "心悸",
    "头痛", "头晕", "恶心", "呕吐", "腹痛", "腹胀", "腹泻", "便秘", "黑便", "尿频", "尿急",
    "尿痛", "血尿", "腰痛", "皮疹", "瘙痒", "关节痛", "麻木", "乏力", "水肿", "失眠",
    "焦虑", "情绪低落", "月经不规律", "白带异常", "牙痛", "眼红", "耳痛",
]

ALIASES = {
    "感冒": ["普通感冒", "流行性感冒", "鼻塞", "流涕"],
    "流清涕": ["流涕", "普通感冒", "过敏性鼻炎"],
    "清鼻涕": ["流涕", "普通感冒", "过敏性鼻炎"],
    "流鼻涕": ["流涕", "普通感冒", "过敏性鼻炎"],
    "血压高": ["高血压"],
    "血糖高": ["2型糖尿病", "糖尿病前期"],
    "嗓子疼": ["咽痛", "急性咽炎", "急性扁桃体炎"],
    "喉咙痛": ["咽痛", "急性咽炎", "急性扁桃体炎"],
    "拉肚子": ["腹泻", "急性胃肠炎"],
    "肚子疼": ["腹痛"],
    "心慌": ["心悸", "房颤", "早搏"],
}


@dataclass(frozen=True)
class MedicalCard:
    record_id: str
    system: str
    disease: str
    scenario: str
    keywords: tuple[str, ...]
    content: str
    source_file: str


@dataclass
class CorpusState:
    cards: list[MedicalCard]
    index: dict[str, list[int]]
    diseases: set[str]
    files: list[Path]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def get_builtin_corpus_dir() -> Path:
    configured = os.getenv("BUILTIN_MEDICAL_CORPUS_DIR")
    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            return configured_path

        root = _project_root()
        backend_root = root / "backend"
        for candidate in (root / configured_path, backend_root / configured_path):
            if candidate.exists():
                return candidate
        return root / configured_path
    return _project_root() / "docs" / "rag_test_corpus" / "split_100k"


def builtin_medical_enabled() -> bool:
    return os.getenv("BUILTIN_MEDICAL_CORPUS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def is_builtin_medical_filename(filename: str | None) -> bool:
    if not filename:
        return False
    return filename in {BUILTIN_FILENAME, BUILTIN_DISPLAY_NAME} or filename.startswith("内置医疗知识库")


def _iter_corpus_files(corpus_dir: Path | None = None) -> list[Path]:
    root = corpus_dir or get_builtin_corpus_dir()
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return sorted(root.glob("*.md"))


def _parse_card(chunk: str, source_file: str) -> MedicalCard | None:
    title = chunk.splitlines()[0] if chunk else ""
    match = TITLE_PATTERN.match(title)
    if not match:
        return None

    keyword_match = KEYWORD_PATTERN.search(chunk)
    keywords: tuple[str, ...] = ()
    if keyword_match:
        keywords = tuple(
            item.strip()
            for item in re.split(r"[,，]\s*", keyword_match.group("keywords"))
            if item.strip()
        )

    data = match.groupdict()
    return MedicalCard(
        record_id=data["record_id"],
        system=data["system"],
        disease=data["disease"],
        scenario=data["scenario"],
        keywords=keywords,
        content=chunk,
        source_file=source_file,
    )


def _extract_terms(query: str, diseases: set[str] | None = None) -> list[str]:
    normalized = query.strip()
    terms: list[str] = []

    for source, additions in ALIASES.items():
        if source in normalized:
            terms.extend(additions)
            normalized = normalized.replace(source, additions[0])

    if diseases:
        terms.extend([disease for disease in diseases if disease and disease in normalized])

    terms.extend([term for term in SYMPTOM_TERMS if term in normalized])
    terms.extend(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", normalized))

    stopwords = {
        "患者", "应该", "怎么", "如何", "判断", "处理", "治疗", "诊疗", "建议", "需要",
        "是否", "可以", "一下", "什么", "哪些", "怎么办", "情况", "现在", "今天",
    }
    cleaned: list[str] = []
    for term in terms:
        term = term.strip()
        if len(term) < 2 or term in stopwords:
            continue
        if term not in cleaned:
            cleaned.append(term)
    return cleaned[:20]


def _load_state(corpus_dir: Path) -> CorpusState:
    cards: list[MedicalCard] = []
    index: dict[str, list[int]] = {}
    diseases: set[str] = set()
    files = _iter_corpus_files(corpus_dir)

    for path in files:
        text = path.read_text(encoding="utf-8")
        chunks = [chunk.strip() for chunk in CARD_PATTERN.split(text) if chunk.strip().startswith("### MED-")]
        for chunk in chunks:
            card = _parse_card(chunk, path.name)
            if not card:
                continue
            card_index = len(cards)
            cards.append(card)
            diseases.add(card.disease)

            index_terms = {
                card.record_id,
                card.system,
                card.disease,
                card.scenario,
                *card.keywords,
            }
            index_terms.update(term for term in SYMPTOM_TERMS if term in card.content)

            for term in index_terms:
                if term:
                    index.setdefault(term, []).append(card_index)

    return CorpusState(cards=cards, index=index, diseases=diseases, files=files)


def get_builtin_medical_corpus_info() -> dict | None:
    if not builtin_medical_enabled():
        return None

    files = _iter_corpus_files()
    if not files:
        return None

    total_count = 0
    for path in files:
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:1000]
            match = COUNT_PATTERN.search(head)
            if match:
                total_count += int(match.group("count"))
            else:
                total_count += path.read_text(encoding="utf-8", errors="ignore").count("### MED-")
        except Exception:
            continue

    return {
        "id": "builtin-medical-corpus",
        "filename": BUILTIN_FILENAME,
        "original_filename": BUILTIN_DISPLAY_NAME,
        "user_id": BUILTIN_USER_ID,
        "chunk_count": total_count,
        "preview": "覆盖呼吸、心血管、消化、内分泌、神经、泌尿、骨科、皮肤、感染、儿科、妇产、五官、心理睡眠等常见病诊疗知识卡。",
        "created_at": None,
    }


class BuiltinMedicalRetriever(BaseRetriever):
    """直接检索仓库内置医疗 Markdown 语料，不需要 Chroma 或 embedding。"""

    corpus_dir: str = ""
    k: int = 8

    _state_cache: ClassVar[dict[str, CorpusState]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def _get_state(self) -> CorpusState:
        corpus_dir = str(Path(self.corpus_dir) if self.corpus_dir else get_builtin_corpus_dir())
        with self._lock:
            if corpus_dir not in self._state_cache:
                self._state_cache[corpus_dir] = _load_state(Path(corpus_dir))
            return self._state_cache[corpus_dir]

    @staticmethod
    def _score(card: MedicalCard, query: str, terms: list[str], seed_score: int) -> int:
        score = seed_score
        title = f"{card.record_id} {card.system} {card.disease} {card.scenario}"
        keyword_text = " ".join(card.keywords)

        for term in terms:
            if term == card.disease:
                score += 150
            elif term in card.disease:
                score += 90
            if term in title:
                score += 40
            if term in keyword_text:
                score += 35
            if term in card.scenario:
                score += 18
            if term in card.system:
                score += 12
            occurrences = card.content.count(term)
            if occurrences:
                score += min(occurrences * 6, 48)

        if card.disease and card.disease in query:
            score += 100
        return score

    def _search(self, query: str) -> list[Document]:
        if not builtin_medical_enabled():
            return []

        state = self._get_state()
        if not state.cards:
            return []

        terms = _extract_terms(query, state.diseases)
        if not terms:
            return []

        candidates: dict[int, int] = {}
        for term in terms:
            for card_index in state.index.get(term, []):
                candidates[card_index] = candidates.get(card_index, 0) + 30

        if not candidates:
            for idx, card in enumerate(state.cards[:5000]):
                if any(term in card.content for term in terms[:5]):
                    candidates[idx] = 10

        scored: list[tuple[int, int]] = []
        for card_index, seed_score in candidates.items():
            card = state.cards[card_index]
            score = self._score(card, query, terms, seed_score)
            if score > 0:
                scored.append((score, card_index))

        scored.sort(reverse=True)
        documents: list[Document] = []
        for _, card_index in scored[: self.k]:
            card = state.cards[card_index]
            documents.append(
                Document(
                    page_content=card.content,
                    metadata={
                        "record_id": card.record_id,
                        "system": card.system,
                        "disease": card.disease,
                        "scenario": card.scenario,
                        "source": card.source_file,
                        "original_filename": BUILTIN_DISPLAY_NAME,
                        "filename": BUILTIN_FILENAME,
                        "user_id": BUILTIN_USER_ID,
                        "retrieval": "builtin_medical_keyword",
                    },
                )
            )
        return documents

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        return self._search(query)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        return self._search(query)


def get_builtin_medical_document_detail(filename: str) -> dict | None:
    if not is_builtin_medical_filename(filename):
        return None

    retriever = BuiltinMedicalRetriever(k=20)
    state = retriever._get_state()
    cards = state.cards[:20]
    content = (
        "内置医疗语料共包含约 100000 条知识卡。为避免前端一次渲染过大，详情页只展示前 20 条样例；"
        "聊天检索会在全部语料中检索。\n\n"
        + "\n\n".join(card.content for card in cards)
    )
    return {
        "id": "builtin-medical-corpus",
        "filename": BUILTIN_FILENAME,
        "user_id": BUILTIN_USER_ID,
        "chunk_count": len(state.cards),
        "content": content,
        "images": [],
        "chunks": [
            {
                "chunk_id": card.record_id,
                "index": index,
                "content": card.content,
                "page": None,
                "images": [],
            }
            for index, card in enumerate(cards)
        ],
        "created_at": None,
    }


def get_builtin_medical_chunks(filename: str, limit: int = 100) -> dict | None:
    if not is_builtin_medical_filename(filename):
        return None

    retriever = BuiltinMedicalRetriever(k=limit)
    state = retriever._get_state()
    cards = state.cards[:limit]
    return {
        "filename": BUILTIN_FILENAME,
        "total_chunks": len(state.cards),
        "chunks": [
            {
                "chunk_id": card.record_id,
                "index": index,
                "content": card.content,
                "metadata": {
                    "record_id": card.record_id,
                    "system": card.system,
                    "disease": card.disease,
                    "scenario": card.scenario,
                    "source": card.source_file,
                    "original_filename": BUILTIN_DISPLAY_NAME,
                    "filename": BUILTIN_FILENAME,
                    "user_id": BUILTIN_USER_ID,
                },
                "images": [],
            }
            for index, card in enumerate(cards)
        ],
    }
