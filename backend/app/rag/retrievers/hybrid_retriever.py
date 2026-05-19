import asyncio
import os
import re
import sqlite3
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.retrievers import BM25Retriever

from app.utils.config import chroma_config
from app.utils.path_tool import get_abstract_path

from .builtin_medical_retriever import BuiltinMedicalRetriever, builtin_medical_enabled, get_builtin_corpus_dir
from .empty_retriever import EmptyRetriever


SYMPTOM_TERMS = [
    "发热", "咳嗽", "咳痰", "鼻塞", "流涕", "咽痛", "喘息", "胸闷", "胸痛", "气短", "心悸",
    "头痛", "头晕", "恶心", "呕吐", "腹痛", "腹胀", "腹泻", "便秘", "黑便", "尿频", "尿急",
    "尿痛", "血尿", "腰痛", "皮疹", "瘙痒", "关节痛", "麻木", "乏力", "水肿", "失眠",
    "焦虑", "情绪低落", "月经不规律", "白带异常", "牙痛", "眼红", "耳痛",
]

ALIASES = {
    "流清涕": ["流涕", "普通感冒", "过敏性鼻炎"],
    "清鼻涕": ["流涕", "普通感冒", "过敏性鼻炎"],
    "流鼻涕": ["流涕", "普通感冒", "过敏性鼻炎"],
    "血压高": ["高血压"],
    "血糖高": ["2型糖尿病", "糖尿病前期"],
    "嗓子疼": ["咽痛", "急性咽炎", "急性扁桃体炎"],
    "喉咙痛": ["咽痛", "急性咽炎", "急性扁桃体炎"],
    "拉肚子": ["腹泻", "急性胃肠炎"],
    "肚子疼": ["腹痛"],
    "心慌": ["心悸"],
}

SHARED_MEDICAL_USER_ID = os.getenv("SHARED_MEDICAL_USER_ID", "agYcn9m9kHM9AHaHMEcRby")


class SQLiteKeywordRetriever(BaseRetriever):
    """面向大规模本地 Chroma 的中文关键词检索器，避免全量 BM25 构建。"""

    db_path: str
    user_id: str
    k: int = 8

    def _connect(self):
        return sqlite3.connect(f"file:{self.db_path.replace(os.sep, '/')}?mode=ro", uri=True, timeout=30)

    def _load_diseases(self) -> list[str]:
        query = """
            SELECT DISTINCT disease.string_value
            FROM embedding_metadata disease
            JOIN embedding_metadata user_meta ON disease.id = user_meta.id
            WHERE disease.key = 'disease'
              AND disease.string_value IS NOT NULL
              AND user_meta.key = 'user_id'
              AND user_meta.string_value = ?
        """
        with self._connect() as conn:
            return [row[0] for row in conn.execute(query, (self.user_id,)).fetchall()]

    def _extract_terms(self, query: str) -> list[str]:
        normalized = query.strip()
        terms: list[str] = []

        for source, additions in ALIASES.items():
            if source in normalized:
                terms.extend(additions)
                normalized = normalized.replace(source, additions[0])

        try:
            terms.extend([disease for disease in self._load_diseases() if disease and disease in normalized])
        except Exception:
            pass

        terms.extend([term for term in SYMPTOM_TERMS if term in normalized])
        terms.extend(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,8}", normalized))

        stopwords = {
            "患者", "应该", "怎么", "如何", "判断", "处理", "治疗", "诊疗", "建议", "需要",
            "是否", "可以", "一下", "什么", "哪些", "怎么办", "情况",
        }
        cleaned = []
        for term in terms:
            term = term.strip()
            if len(term) < 2 or term in stopwords:
                continue
            if term not in cleaned:
                cleaned.append(term)
        return cleaned[:16]

    def _extract_disease_terms(self, query: str, terms: list[str]) -> list[str]:
        """提取可直接命中 disease metadata 的词，作为最高优先级召回入口。"""
        disease_terms: list[str] = []
        disease_set = set()

        try:
            disease_set = {disease for disease in self._load_diseases() if disease}
        except Exception:
            disease_set = set()

        normalized = query.strip()
        for source, additions in ALIASES.items():
            if source in normalized:
                disease_terms.extend([item for item in additions if item in disease_set])
                normalized = normalized.replace(source, additions[0])

        disease_terms.extend([disease for disease in disease_set if disease in normalized])
        disease_terms.extend([term for term in terms if term in disease_set])

        unique_terms = []
        for term in disease_terms:
            if term and term not in unique_terms:
                unique_terms.append(term)
        return unique_terms[:8]

    def _build_meta_sql(self, where_clause: str, limit: int) -> str:
        return f"""
            WITH user_docs AS (
                SELECT e.id, e.embedding_id
                FROM embeddings e
                JOIN embedding_metadata user_meta
                  ON e.id = user_meta.id
                 AND user_meta.key = 'user_id'
                 AND user_meta.string_value = ?
            ),
            meta AS (
                SELECT
                    user_docs.id,
                    user_docs.embedding_id,
                    MAX(CASE WHEN m.key = 'chroma:document' THEN m.string_value END) AS document,
                    MAX(CASE WHEN m.key = 'record_id' THEN m.string_value END) AS record_id,
                    MAX(CASE WHEN m.key = 'system' THEN m.string_value END) AS system,
                    MAX(CASE WHEN m.key = 'disease' THEN m.string_value END) AS disease,
                    MAX(CASE WHEN m.key = 'scenario' THEN m.string_value END) AS scenario,
                    MAX(CASE WHEN m.key = 'source' THEN m.string_value END) AS source,
                    MAX(CASE WHEN m.key = 'original_filename' THEN m.string_value END) AS original_filename,
                    MAX(CASE WHEN m.key = 'filename' THEN m.string_value END) AS filename,
                    MAX(CASE WHEN m.key = 'md5' THEN m.string_value END) AS md5
                FROM user_docs
                JOIN embedding_metadata m ON user_docs.id = m.id
                GROUP BY user_docs.id, user_docs.embedding_id
            )
            SELECT *
            FROM meta
            WHERE {where_clause}
            LIMIT {limit}
        """

    def _score(self, query: str, terms: list[str], metadata: dict, content: str) -> int:
        score = 0
        disease = metadata.get("disease") or ""
        scenario = metadata.get("scenario") or ""
        system = metadata.get("system") or ""
        title = content.splitlines()[0] if content else ""

        for term in terms:
            if term == disease:
                score += 120
            elif term in disease:
                score += 80
            if term in title:
                score += 35
            if term in scenario:
                score += 15
            if term in system:
                score += 10
            occurrences = content.count(term)
            if occurrences:
                score += min(occurrences * 8, 40)

        if disease and disease in query:
            score += 80
        return score

    def _rows_to_documents(self, rows, query: str, terms: list[str]) -> list[tuple[int, Document]]:
        scored: list[tuple[int, Document]] = []
        for row in rows:
            content = row["document"] or ""
            metadata = {
                "record_id": row["record_id"],
                "system": row["system"],
                "disease": row["disease"],
                "scenario": row["scenario"],
                "source": row["source"],
                "original_filename": row["original_filename"],
                "filename": row["filename"],
                "md5": row["md5"],
                "user_id": self.user_id,
                "retrieval": "sqlite_keyword",
            }
            score = self._score(query, terms, metadata, content)
            if score > 0:
                scored.append((score, Document(page_content=content, metadata=metadata)))
        return scored

    def _search(self, query: str) -> list[Document]:
        if not self.user_id or not os.path.exists(self.db_path):
            return []

        terms = self._extract_terms(query)
        if not terms:
            return []

        disease_terms = self._extract_disease_terms(query, terms)
        rows_by_id = {}
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            for disease in disease_terms:
                sql = self._build_meta_sql("disease = ?", 120)
                for row in conn.execute(sql, [self.user_id, disease]).fetchall():
                    rows_by_id[row["embedding_id"]] = row

            for disease in disease_terms:
                sql = self._build_meta_sql("disease LIKE ?", 80)
                for row in conn.execute(sql, [self.user_id, f"%{disease}%"]).fetchall():
                    rows_by_id.setdefault(row["embedding_id"], row)

            symptom_terms = [term for term in terms if term not in disease_terms]
            for term in symptom_terms[:8]:
                like = f"%{term}%"
                sql = self._build_meta_sql(
                    "disease LIKE ? OR scenario LIKE ? OR system LIKE ? OR document LIKE ?",
                    50,
                )
                for row in conn.execute(sql, [self.user_id, like, like, like, like]).fetchall():
                    rows_by_id.setdefault(row["embedding_id"], row)

            if not rows_by_id and len(symptom_terms) >= 2:
                clauses = " AND ".join(["document LIKE ?" for _ in symptom_terms[:3]])
                sql = self._build_meta_sql(clauses, 100)
                params = [self.user_id, *[f"%{term}%" for term in symptom_terms[:3]]]
                for row in conn.execute(sql, params).fetchall():
                    rows_by_id[row["embedding_id"]] = row

        scored = self._rows_to_documents(rows_by_id.values(), query, terms)

        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:self.k]]

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        return self._search(query)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        return await asyncio.to_thread(self._search, query)


class CombinedKeywordRetriever(BaseRetriever):
    retrievers: list[BaseRetriever]
    k: int = 8

    @staticmethod
    def _merge(doc_groups: list[list[Document]], k: int) -> list[Document]:
        merged: list[Document] = []
        seen = set()
        for docs in doc_groups:
            for doc in docs:
                key = (
                    doc.metadata.get("record_id"),
                    doc.metadata.get("source"),
                    doc.page_content[:120],
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(doc)
                if len(merged) >= k:
                    return merged
        return merged

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        doc_groups = []
        for retriever in self.retrievers:
            try:
                doc_groups.append(retriever.invoke(query))
            except Exception:
                doc_groups.append([])
        return self._merge(doc_groups, self.k)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        results = await asyncio.gather(
            *[retriever.ainvoke(query) for retriever in self.retrievers],
            return_exceptions=True,
        )
        doc_groups = [result if not isinstance(result, Exception) else [] for result in results]
        return self._merge(doc_groups, self.k)


class LocalHybridRetriever(BaseRetriever):
    vector_retriever: BaseRetriever
    keyword_retriever: BaseRetriever
    k: int = 8

    @staticmethod
    def _merge(primary: list[Document], secondary: list[Document], k: int) -> list[Document]:
        merged: list[Document] = []
        seen = set()
        for doc in [*primary, *secondary]:
            key = (
                doc.metadata.get("record_id"),
                doc.metadata.get("source"),
                doc.page_content[:120],
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(doc)
            if len(merged) >= k:
                break
        return merged

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        try:
            keyword_docs = self.keyword_retriever.invoke(query)
        except Exception:
            keyword_docs = []

        try:
            vector_docs = self.vector_retriever.invoke(query)
        except Exception:
            vector_docs = []

        return self._merge(keyword_docs, vector_docs, self.k)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        keyword_task = asyncio.create_task(self.keyword_retriever.ainvoke(query))
        vector_task = asyncio.create_task(self.vector_retriever.ainvoke(query))
        keyword_docs, vector_docs = await asyncio.gather(keyword_task, vector_task, return_exceptions=True)
        if isinstance(keyword_docs, Exception):
            keyword_docs = []
        if isinstance(vector_docs, Exception):
            vector_docs = []
        return self._merge(keyword_docs, vector_docs, self.k)


class CombinedRetriever(BaseRetriever):
    retrievers: list[BaseRetriever]
    k: int = 8

    @staticmethod
    def _merge(doc_groups: list[list[Document]], k: int) -> list[Document]:
        merged: list[Document] = []
        seen = set()
        for docs in doc_groups:
            for doc in docs:
                key = (
                    doc.metadata.get("record_id"),
                    doc.metadata.get("source"),
                    doc.page_content[:120],
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(doc)
                if len(merged) >= k:
                    return merged
        return merged

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        doc_groups = []
        for retriever in self.retrievers:
            try:
                doc_groups.append(retriever.invoke(query))
            except Exception:
                doc_groups.append([])
        return self._merge(doc_groups, self.k)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        results = await asyncio.gather(
            *[retriever.ainvoke(query) for retriever in self.retrievers],
            return_exceptions=True,
        )
        doc_groups = [result if not isinstance(result, Exception) else [] for result in results]
        return self._merge(doc_groups, self.k)


class HybridRetriever:
    """混合检索器（BM25 + 向量检索）"""

    def __init__(self, vectors_store: Chroma):
        self.vectors_store = vectors_store

    @staticmethod
    def _has_chroma_documents(db_path: str, user_ids: list[str]) -> bool:
        if not os.path.exists(db_path):
            return False

        placeholders = ",".join(["?"] * len(user_ids))
        query = f"""
            SELECT 1
            FROM embedding_metadata
            WHERE key = 'user_id'
              AND string_value IN ({placeholders})
            LIMIT 1
        """
        try:
            with sqlite3.connect(f"file:{db_path.replace(os.sep, '/')}?mode=ro", uri=True, timeout=10) as conn:
                return conn.execute(query, user_ids).fetchone() is not None
        except Exception:
            return False

    async def get_bm25_retriever(self, user_id: str = None):
        """
        获取BM25检索器
        :param user_id: 用户ID，必须提供，否则返回None
        :return: BM25Retriever实例
        """
        if not user_id:
            return None

        all_docs_result = await asyncio.to_thread(
            self.vectors_store.get,
            include=['documents', 'metadatas'],
            where={'user_id': user_id}
        )
        documents = []
        for i, doc_content in enumerate(all_docs_result['documents']):
            metadata = all_docs_result['metadatas'][i] if i < len(all_docs_result['metadatas']) else {}
            documents.append(Document(page_content=doc_content, metadata=metadata))

        if documents:
            bm25_retriever = BM25Retriever.from_documents(
                documents=documents,
                k=chroma_config['k']
            )
            return bm25_retriever
        else:
            return None

    async def _get_all_documents(self) -> list[Document]:
        """
        获取向量库中的所有文档
        :return: 文档列表
        """
        all_docs = await asyncio.to_thread(
            self.vectors_store.get,
            include=['documents', 'metadatas']
        )
        documents = []
        for i, doc in enumerate(all_docs['documents']):
            metadata = all_docs['metadatas'][i] if i < len(all_docs['metadatas']) else {}
            documents.append(Document(page_content=doc, metadata=metadata))
        return documents

    async def get_retriever(self, query: str = None, user_id: str = None) -> BaseRetriever:
        """
        获取混合检索器（BM25 + 向量检索）
        :param query: 查询语句，用于动态调整权重
        :param user_id: 用户ID，用于过滤用户的文档，为空时不返回任何文档
        :return: EnsembleRetriever实例或单独的向量检索器
        """
        if not user_id:
            return EmptyRetriever()

        k = max(int(chroma_config.get('k', 5)), 8)
        user_ids = [user_id]
        if SHARED_MEDICAL_USER_ID and SHARED_MEDICAL_USER_ID not in user_ids:
            user_ids.append(SHARED_MEDICAL_USER_ID)

        if len(user_ids) == 1:
            filter_dict = {'user_id': user_ids[0]}
        else:
            filter_dict = {'$or': [{'user_id': item} for item in user_ids]}

        vector_retriever = self.vectors_store.as_retriever(
            search_type='similarity',
            search_kwargs={'k': k, 'filter': filter_dict},
        )
        persist_dir = get_abstract_path(chroma_config['persist_directory'])
        db_path = os.path.join(persist_dir, "chroma.sqlite3")

        if builtin_medical_enabled() and not self._has_chroma_documents(db_path, user_ids):
            return BuiltinMedicalRetriever(corpus_dir=str(get_builtin_corpus_dir()), k=k)

        keyword_retriever = CombinedKeywordRetriever(
            retrievers=[
                SQLiteKeywordRetriever(
                    db_path=db_path,
                    user_id=current_user_id,
                    k=k,
                )
                for current_user_id in user_ids
            ],
            k=k,
        )
        local_retriever = LocalHybridRetriever(
            vector_retriever=vector_retriever,
            keyword_retriever=keyword_retriever,
            k=k,
        )

        if builtin_medical_enabled():
            return CombinedRetriever(
                retrievers=[
                    BuiltinMedicalRetriever(corpus_dir=str(get_builtin_corpus_dir()), k=k),
                    local_retriever,
                ],
                k=k,
            )

        return local_retriever

    @staticmethod
    async def get_dynamic_weights(query: str = None):
        """
        根据查询动态调整权重
        :param query: 查询语句
        :return: 权重列表 [向量检索权重, BM25检索权重]
        """
        default_vector_weight = 0.5
        default_bm25_weight = 0.5

        if not query:
            return [default_vector_weight, default_bm25_weight]

        query_length = len(query)
        query_words = len(query.split())
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', query))
        chinese_ratio = chinese_chars / max(query_length, 1)

        if chinese_ratio > 0.35:
            return [0.8, 0.2]

        if query_length > 50:
            vector_weight = 0.7
            bm25_weight = 0.3
        elif query_length < 20:
            vector_weight = 0.3
            bm25_weight = 0.7
        else:
            vector_weight = default_vector_weight
            bm25_weight = default_bm25_weight

        if query_words > 0:
            word_density = query_words / query_length
            if word_density > 0.1:
                bm25_weight = min(bm25_weight + 0.1, 0.7)
                vector_weight = max(vector_weight - 0.1, 0.3)

        return [vector_weight, bm25_weight]
