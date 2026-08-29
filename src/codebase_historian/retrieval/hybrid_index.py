"""
Hybrid retrieval index using ChromaDB (vector) and lexical keyword matching.
Indexes commit messages, pull request discussions, and AST docstrings.
"""

import math
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import chromadb
from chromadb.api import ClientAPI

from codebase_historian.graph.models import PullRequestNodeData
from codebase_historian.ingestion.models import CommitRecord, FileStructureRecord
from codebase_historian.ingestion.pipeline import IngestionResult
from codebase_historian.retrieval.models import DocumentType, IndexedDocument, SearchResult


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words."""
    return re.findall(r"\b\w+\b", text.lower())


class LexicalMatcher:
    """Computes BM25-inspired keyword matching scores across indexed documents."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens: Dict[str, List[str]] = {}
        self.doc_lengths: Dict[str, int] = {}
        self.avg_doc_len: float = 0.0
        self.df: Dict[str, int] = {}
        self.num_docs: int = 0

    def add_documents(self, docs: List[IndexedDocument]) -> None:
        """Add documents to lexical index."""
        for doc in docs:
            tokens = tokenize(doc.text)
            self.doc_tokens[doc.id] = tokens
            self.doc_lengths[doc.id] = len(tokens)
            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.df[t] = self.df.get(t, 0) + 1

        self.num_docs = len(self.doc_tokens)
        total_len = sum(self.doc_lengths.values())
        self.avg_doc_len = (total_len / self.num_docs) if self.num_docs > 0 else 0.0

    def score(self, query: str) -> Dict[str, float]:
        """Score all documents against query using BM25 with exact phrase bonus."""
        q_tokens = tokenize(query)
        if not q_tokens or self.num_docs == 0:
            return {}

        q_lower = query.lower().strip()
        scores: Dict[str, float] = {}

        for doc_id, tokens in self.doc_tokens.items():
            doc_len = self.doc_lengths.get(doc_id, 0)
            score = 0.0
            term_counts: Dict[str, int] = {}
            for t in tokens:
                term_counts[t] = term_counts.get(t, 0) + 1

            for q_term in q_tokens:
                if q_term not in term_counts:
                    continue
                tf = term_counts[q_term]
                doc_freq = self.df.get(q_term, 0)
                # Standard BM25 IDF
                idf = math.log(1 + (self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5))
                denom = tf + self.k1 * (1 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
                score += idf * ((tf * (self.k1 + 1)) / (denom or 1.0))

            # Bonus for exact substring match
            doc_text = " ".join(tokens)
            if q_lower in doc_text:
                score += 2.0

            if score > 0:
                scores[doc_id] = score

        # Normalize scores to [0, 1] range
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                for d_id in scores:
                    scores[d_id] = scores[d_id] / max_score

        return scores

    def clear(self) -> None:
        self.doc_tokens.clear()
        self.doc_lengths.clear()
        self.df.clear()
        self.num_docs = 0
        self.avg_doc_len = 0.0


class HybridRetrievalIndex:
    """
    Combines ChromaDB vector retrieval with lexical keyword search.
    Provides indexing and hybrid search over commits, PRs, and docstrings.
    """

    COLLECTION_NAME = "codebase_historian"

    def __init__(
        self,
        persist_directory: Optional[str | Path] = None,
        chroma_client: Optional[ClientAPI] = None,
        embedding_function: Optional[Any] = None,
        alpha: float = 0.6,  # Weight for vector score (1 - alpha for keyword score)
    ):
        self.alpha = alpha
        self.persist_directory = str(persist_directory) if persist_directory else None

        if chroma_client is not None:
            self.client = chroma_client
        elif self.persist_directory:
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.persist_directory)
        else:
            self.client = chromadb.EphemeralClient()

        self.embedding_function = embedding_function
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        self.lexical_index = LexicalMatcher()
        self.docs_by_id: Dict[str, IndexedDocument] = {}

    def index_documents(self, documents: List[IndexedDocument]) -> None:
        """Add documents to both ChromaDB collection and lexical index."""
        if not documents:
            return

        ids = [d.id for d in documents]
        texts = [d.text for d in documents]
        metadatas = [
            {
                "doc_type": d.doc_type.value,
                "subject": d.subject,
                **{k: str(v) if isinstance(v, (list, dict)) else v for k, v in d.metadata.items()},
            }
            for d in documents
        ]

        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
        )

        for d in documents:
            self.docs_by_id[d.id] = d

        self.lexical_index.add_documents(documents)

    def index_commits(self, commits: List[CommitRecord]) -> None:
        """Index commit messages with author and file modification metadata."""
        docs: List[IndexedDocument] = []
        for c in commits:
            touched_files = [m.path for m in c.modifications]
            file_list_str = ", ".join(touched_files)
            body = f"Commit {c.sha[:8]} by {c.author.display_name}: {c.message}\nModified files: {file_list_str}"
            subject = touched_files[0] if touched_files else "repository"

            docs.append(
                IndexedDocument(
                    id=f"commit:{c.sha}",
                    text=body,
                    doc_type=DocumentType.COMMIT,
                    subject=subject,
                    metadata={
                        "sha": c.sha,
                        "author": c.author.display_name,
                        "author_id": c.author.id,
                        "timestamp": c.timestamp.isoformat(),
                        "files_count": len(touched_files),
                    },
                )
            )
        self.index_documents(docs)

    def index_pull_requests(self, prs: List[PullRequestNodeData]) -> None:
        """Index PR titles, descriptions, and metadata."""
        docs: List[IndexedDocument] = []
        for pr in prs:
            text = f"Pull Request #{pr.number}: {pr.title}\n{pr.description or ''}"
            docs.append(
                IndexedDocument(
                    id=f"pr:{pr.number}",
                    text=text,
                    doc_type=DocumentType.PULL_REQUEST,
                    subject=f"PR #{pr.number}",
                    metadata={
                        "number": pr.number,
                        "title": pr.title,
                        "author": pr.author,
                        "status": pr.status,
                    },
                )
            )
        self.index_documents(docs)

    def index_file_structures(self, structures: List[FileStructureRecord]) -> None:
        """Index docstrings extracted from modules, classes, and functions."""
        docs: List[IndexedDocument] = []
        for s in structures:
            # 1. Module docstring
            if s.docstring:
                docs.append(
                    IndexedDocument(
                        id=f"docstring:{s.path}:module",
                        text=f"Module {s.path}:\n{s.docstring}",
                        doc_type=DocumentType.DOCSTRING,
                        subject=s.path,
                        metadata={"file": s.path, "symbol": s.path, "kind": "module"},
                    )
                )

            # 2. Class docstrings
            for cls in s.classes:
                if cls.docstring:
                    docs.append(
                        IndexedDocument(
                            id=f"docstring:{s.path}:{cls.qualname}",
                            text=f"Class {cls.qualname} in {s.path}:\n{cls.docstring}",
                            doc_type=DocumentType.DOCSTRING,
                            subject=f"{s.path}:{cls.qualname}",
                            metadata={"file": s.path, "symbol": cls.qualname, "kind": "class"},
                        )
                    )
                # Method docstrings
                for m in cls.methods:
                    if m.docstring:
                        docs.append(
                            IndexedDocument(
                                id=f"docstring:{s.path}:{m.qualname}",
                                text=f"Method {m.qualname} in {s.path}:\n{m.docstring}",
                                doc_type=DocumentType.DOCSTRING,
                                subject=f"{s.path}:{m.qualname}",
                                metadata={"file": s.path, "symbol": m.qualname, "kind": "method"},
                            )
                        )

            # 3. Top-level function docstrings
            for fn in s.functions:
                if fn.docstring:
                    docs.append(
                        IndexedDocument(
                            id=f"docstring:{s.path}:{fn.qualname}",
                            text=f"Function {fn.qualname} in {s.path}:\n{fn.docstring}",
                            doc_type=DocumentType.DOCSTRING,
                            subject=f"{s.path}:{fn.qualname}",
                            metadata={"file": s.path, "symbol": fn.qualname, "kind": "function"},
                        )
                    )
        self.index_documents(docs)

    def index_ingestion_result(
        self,
        result: IngestionResult,
        pull_requests: Optional[List[PullRequestNodeData]] = None,
    ) -> None:
        """Index full ingestion output (commits, AST docstrings) and optional PRs."""
        self.index_commits(result.commits)
        self.index_file_structures(result.file_structures)
        if pull_requests:
            self.index_pull_requests(pull_requests)

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_type: Optional[DocumentType] = None,
        subject_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Execute hybrid search combining vector distance and keyword relevance.
        Supports filtering by document type and subject prefix.
        """
        if not self.docs_by_id:
            return []

        # 1. Lexical Keyword Scores
        keyword_scores = self.lexical_index.score(query)

        # 2. Vector Semantic Scores from ChromaDB
        where_filter = {}
        if doc_type:
            where_filter["doc_type"] = doc_type.value

        vector_scores: Dict[str, float] = {}
        try:
            # Query more candidates from vector store to fuse with keyword results
            n_results = min(max(top_k * 3, 20), len(self.docs_by_id))
            query_kwargs: Dict[str, Any] = {
                "query_texts": [query],
                "n_results": n_results,
            }
            if where_filter:
                query_kwargs["where"] = where_filter

            v_res = self.collection.query(**query_kwargs)

            if v_res and v_res.get("ids") and v_res["ids"][0]:
                for doc_id, distance in zip(v_res["ids"][0], v_res["distances"][0]):
                    # Convert cosine distance (0..2) to similarity score (0..1)
                    # cosine similarity = 1 - distance
                    sim = max(0.0, 1.0 - (distance / 2.0))
                    vector_scores[doc_id] = sim
        except Exception:
            # If vector search fails (e.g. empty collection), proceed with keyword scores
            vector_scores = {}

        # 3. Fuse scores
        all_candidate_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        if not all_candidate_ids:
            # Fallback: search doc texts directly for exact matches
            for d_id, doc in self.docs_by_id.items():
                if query.lower() in doc.text.lower():
                    all_candidate_ids.add(d_id)

        results: List[SearchResult] = []
        for doc_id in all_candidate_ids:
            doc = self.docs_by_id.get(doc_id)
            if not doc:
                continue

            # Apply filters
            if doc_type and doc.doc_type != doc_type:
                continue
            if subject_filter and subject_filter.lower() not in doc.subject.lower():
                continue

            v_score = vector_scores.get(doc_id, 0.0)
            k_score = keyword_scores.get(doc_id, 0.0)

            # Combined hybrid score
            if v_score > 0 and k_score > 0:
                hybrid_score = (self.alpha * v_score) + ((1.0 - self.alpha) * k_score)
            elif v_score > 0:
                hybrid_score = self.alpha * v_score
            else:
                hybrid_score = (1.0 - self.alpha) * k_score

            results.append(
                SearchResult(
                    id=doc.id,
                    text=doc.text,
                    doc_type=doc.doc_type,
                    subject=doc.subject,
                    score=round(hybrid_score, 4),
                    vector_score=round(v_score, 4) if v_score else None,
                    keyword_score=round(k_score, 4) if k_score else None,
                    metadata=doc.metadata,
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def count(self) -> int:
        """Return total number of indexed documents."""
        return len(self.docs_by_id)

    def clear(self) -> None:
        """Clear all documents from collection and lexical index."""
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        self.lexical_index.clear()
        self.docs_by_id.clear()
