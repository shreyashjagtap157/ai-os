"""
Vector Store for Retrieval-Augmented Generation (RAG)

Implements semantic search and embedding storage for intelligent
context retrieval, enabling the AI to access relevant information
from a knowledge base.

Features:
- Multiple embedding provider support (OpenAI, local)
- Efficient similarity search with HNSW indexing
- Document chunking and metadata storage
- Hybrid search (semantic + keyword)
- Persistent storage with SQLite + numpy
"""

import hashlib
import json
import logging
import os
import pickle
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
import re

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A document in the vector store"""
    id: str
    content: str
    embedding: Optional[np.ndarray] = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class SearchResult:
    """A search result with relevance score"""
    document: Document
    score: float
    highlights: list[str] = field(default_factory=list)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension"""
        pass
    
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings for a list of texts"""
        pass
    
    @abstractmethod
    async def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        pass


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI text-embedding-3-small provider"""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self._dimension = 1536 if "small" in model else 3072
        
    @property
    def dimension(self) -> int:
        return self._dimension
    
    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={"input": texts, "model": self.model}
            ) as resp:
                data = await resp.json()
                
                if "error" in data:
                    raise RuntimeError(f"OpenAI API error: {data['error']}")
                
                embeddings = [
                    np.array(item["embedding"], dtype=np.float32)
                    for item in sorted(data["data"], key=lambda x: x["index"])
                ]
                return embeddings
    
    async def embed_single(self, text: str) -> np.ndarray:
        embeddings = await self.embed([text])
        return embeddings[0]


class LocalEmbedding(EmbeddingProvider):
    """Local sentence-transformers embedding provider"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384  # Default for MiniLM
        
    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                logger.warning("sentence-transformers not available, using random embeddings")
                self._model = "random"
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    async def embed(self, texts: list[str]) -> list[np.ndarray]:
        self._load_model()
        
        if self._model == "random":
            # Fallback to deterministic pseudo-random embeddings
            return [self._pseudo_random_embedding(t) for t in texts]
        
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [e.astype(np.float32) for e in embeddings]
    
    async def embed_single(self, text: str) -> np.ndarray:
        embeddings = await self.embed([text])
        return embeddings[0]
    
    def _pseudo_random_embedding(self, text: str) -> np.ndarray:
        """Generate deterministic pseudo-random embedding from text hash"""
        hash_bytes = hashlib.sha256(text.encode()).digest()
        np.random.seed(int.from_bytes(hash_bytes[:4], 'big'))
        return np.random.randn(self._dimension).astype(np.float32)


class TextChunker:
    """Chunk text into smaller pieces for embedding"""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " "]
    
    def chunk(self, text: str, metadata: dict = None) -> list[Document]:
        """Split text into chunks and create documents"""
        chunks = self._recursive_split(text, self.separators)
        
        documents = []
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{text[:100]}_{i}".encode()).hexdigest()[:12]
            doc_metadata = {**(metadata or {}), "chunk_index": i, "total_chunks": len(chunks)}
            
            documents.append(Document(
                id=chunk_id,
                content=chunk.strip(),
                metadata=doc_metadata
            ))
        
        return documents
    
    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text using separators"""
        if not separators:
            # Base case: split by character count
            return self._split_by_size(text)
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        splits = text.split(separator)
        chunks = []
        current_chunk = ""
        
        for split in splits:
            test_chunk = current_chunk + separator + split if current_chunk else split
            
            if len(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                if len(split) > self.chunk_size:
                    # Recursively split with next separator
                    sub_chunks = self._recursive_split(split, remaining_separators)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                else:
                    current_chunk = split
        
        if current_chunk:
            chunks.append(current_chunk)
        
        # Add overlap between chunks
        return self._add_overlap(chunks)
    
    def _split_by_size(self, text: str) -> list[str]:
        """Split text by character count"""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunks.append(text[i:i + self.chunk_size])
        return chunks
    
    def _add_overlap(self, chunks: list[str]) -> list[str]:
        """Add overlap between chunks"""
        if len(chunks) <= 1 or self.chunk_overlap == 0:
            return chunks
        
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_overlap = chunks[i-1][-self.chunk_overlap:] if len(chunks[i-1]) > self.chunk_overlap else chunks[i-1]
            overlapped.append(prev_overlap + chunks[i])
        
        return overlapped


class HNSWIndex:
    """
    Hierarchical Navigable Small World (HNSW) index for approximate nearest neighbor search.
    Simplified implementation for moderate-scale use.
    """
    
    def __init__(self, dimension: int, max_elements: int = 100000, ef_construction: int = 200, M: int = 16):
        self.dimension = dimension
        self.max_elements = max_elements
        self.ef_construction = ef_construction
        self.M = M
        
        # Storage
        self.vectors: list[np.ndarray] = []
        self.ids: list[str] = []
        
        # Try to use hnswlib if available
        self._index = None
        self._use_hnswlib = False
        
        try:
            import hnswlib
            self._index = hnswlib.Index(space='cosine', dim=dimension)
            self._index.init_index(max_elements=max_elements, ef_construction=ef_construction, M=M)
            self._use_hnswlib = True
            logger.info("Using hnswlib for vector search")
        except ImportError:
            logger.info("hnswlib not available, using brute-force search")
    
    def add(self, id: str, vector: np.ndarray):
        """Add a vector to the index"""
        if self._use_hnswlib:
            idx = len(self.ids)
            self._index.add_items(vector.reshape(1, -1), [idx])
        
        self.vectors.append(vector)
        self.ids.append(id)
    
    def search(self, query: np.ndarray, k: int = 10) -> list[tuple[str, float]]:
        """Search for k nearest neighbors"""
        if len(self.vectors) == 0:
            return []
        
        k = min(k, len(self.vectors))
        
        if self._use_hnswlib:
            self._index.set_ef(max(k + 10, 50))
            indices, distances = self._index.knn_query(query.reshape(1, -1), k=k)
            return [(self.ids[idx], 1 - dist) for idx, dist in zip(indices[0], distances[0])]
        
        # Brute-force cosine similarity
        query_norm = query / (np.linalg.norm(query) + 1e-9)
        
        similarities = []
        for i, vec in enumerate(self.vectors):
            vec_norm = vec / (np.linalg.norm(vec) + 1e-9)
            sim = np.dot(query_norm, vec_norm)
            similarities.append((self.ids[i], float(sim)))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]
    
    def remove(self, id: str):
        """Remove a vector from the index (marks as deleted)"""
        if id in self.ids:
            idx = self.ids.index(id)
            if self._use_hnswlib:
                self._index.mark_deleted(idx)
            self.ids[idx] = None  # Mark as deleted
            self.vectors[idx] = None
    
    def save(self, path: str):
        """Save index to disk"""
        with open(path, 'wb') as f:
            pickle.dump({
                'vectors': self.vectors,
                'ids': self.ids,
                'dimension': self.dimension
            }, f)
        
        if self._use_hnswlib:
            self._index.save_index(f"{path}.hnsw")
    
    def load(self, path: str):
        """Load index from disk"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.vectors = data['vectors']
            self.ids = data['ids']
            self.dimension = data['dimension']
        
        if self._use_hnswlib and os.path.exists(f"{path}.hnsw"):
            self._index.load_index(f"{path}.hnsw", max_elements=self.max_elements)


class VectorStore:
    """
    Main vector store for RAG implementation.
    Combines embedding generation, vector indexing, and document storage.
    """
    
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        storage_path: str = ".vector_store",
        chunker: TextChunker = None
    ):
        self.embedding = embedding_provider
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.chunker = chunker or TextChunker()
        self.index = HNSWIndex(dimension=embedding_provider.dimension)
        
        # SQLite for document storage
        self.db_path = self.storage_path / "documents.db"
        self._init_db()
        
        # Load existing index
        index_path = self.storage_path / "index.pkl"
        if index_path.exists():
            self.index.load(str(index_path))
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata TEXT,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts 
            USING fts5(id, content, tokenize='porter')
        """)
        conn.commit()
        conn.close()
    
    async def add_text(
        self,
        text: str,
        metadata: dict = None,
        chunk: bool = True
    ) -> list[str]:
        """Add text to the vector store, optionally chunking it"""
        if chunk:
            documents = self.chunker.chunk(text, metadata)
        else:
            doc_id = hashlib.md5(text.encode()).hexdigest()[:12]
            documents = [Document(id=doc_id, content=text, metadata=metadata or {})]
        
        return await self.add_documents(documents)
    
    async def add_documents(self, documents: list[Document]) -> list[str]:
        """Add multiple documents to the store"""
        # Generate embeddings
        texts = [doc.content for doc in documents]
        embeddings = await self.embedding.embed(texts)
        
        conn = sqlite3.connect(self.db_path)
        ids = []
        
        for doc, emb in zip(documents, embeddings):
            doc.embedding = emb
            
            # Store in SQLite
            conn.execute("""
                INSERT OR REPLACE INTO documents (id, content, metadata, embedding, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                doc.id,
                doc.content,
                json.dumps(doc.metadata),
                emb.tobytes(),
                doc.created_at.isoformat()
            ))
            
            # Update FTS index
            conn.execute("""
                INSERT OR REPLACE INTO documents_fts (id, content)
                VALUES (?, ?)
            """, (doc.id, doc.content))
            
            # Add to vector index
            self.index.add(doc.id, emb)
            ids.append(doc.id)
        
        conn.commit()
        conn.close()
        
        # Save index
        self.index.save(str(self.storage_path / "index.pkl"))
        
        logger.info(f"Added {len(documents)} documents to vector store")
        return ids
    
    async def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict = None,
        hybrid_alpha: float = 0.7
    ) -> list[SearchResult]:
        """
        Search for relevant documents.
        
        Args:
            query: Search query
            k: Number of results
            filter_metadata: Optional metadata filter
            hybrid_alpha: Weight for semantic vs keyword search (1.0 = pure semantic)
        """
        # Semantic search
        query_embedding = await self.embedding.embed_single(query)
        semantic_results = self.index.search(query_embedding, k=k * 2)
        
        # Keyword search (FTS)
        keyword_results = self._keyword_search(query, k=k * 2)
        
        # Hybrid ranking
        combined_scores = {}
        
        for doc_id, score in semantic_results:
            if doc_id:
                combined_scores[doc_id] = hybrid_alpha * score
        
        for doc_id, score in keyword_results:
            if doc_id in combined_scores:
                combined_scores[doc_id] += (1 - hybrid_alpha) * score
            else:
                combined_scores[doc_id] = (1 - hybrid_alpha) * score
        
        # Sort and filter
        sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Fetch documents and apply filters
        results = []
        conn = sqlite3.connect(self.db_path)
        
        for doc_id, score in sorted_results[:k * 2]:
            row = conn.execute(
                "SELECT content, metadata, created_at FROM documents WHERE id = ?",
                (doc_id,)
            ).fetchone()
            
            if row:
                metadata = json.loads(row[1]) if row[1] else {}
                
                # Apply metadata filter
                if filter_metadata:
                    if not all(metadata.get(k) == v for k, v in filter_metadata.items()):
                        continue
                
                doc = Document(
                    id=doc_id,
                    content=row[0],
                    metadata=metadata,
                    created_at=datetime.fromisoformat(row[2])
                )
                
                # Extract highlights
                highlights = self._extract_highlights(doc.content, query)
                
                results.append(SearchResult(
                    document=doc,
                    score=score,
                    highlights=highlights
                ))
                
                if len(results) >= k:
                    break
        
        conn.close()
        return results
    
    def _keyword_search(self, query: str, k: int) -> list[tuple[str, float]]:
        """Perform FTS5 keyword search"""
        conn = sqlite3.connect(self.db_path)
        
        # Escape special FTS characters
        safe_query = re.sub(r'[^\w\s]', ' ', query)
        terms = safe_query.split()
        fts_query = ' OR '.join(terms)
        
        try:
            rows = conn.execute("""
                SELECT id, bm25(documents_fts) as score
                FROM documents_fts
                WHERE documents_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """, (fts_query, k)).fetchall()
            
            # Normalize BM25 scores to 0-1 range
            if rows:
                max_score = abs(min(r[1] for r in rows))
                return [(r[0], abs(r[1]) / max_score if max_score > 0 else 0) for r in rows]
        except sqlite3.OperationalError:
            pass
        
        conn.close()
        return []
    
    def _extract_highlights(self, content: str, query: str, context_chars: int = 100) -> list[str]:
        """Extract relevant snippets from content"""
        query_terms = query.lower().split()
        sentences = re.split(r'[.!?]+', content)
        
        highlights = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(term in sentence_lower for term in query_terms):
                highlight = sentence.strip()[:context_chars * 2]
                if len(sentence) > context_chars * 2:
                    highlight += "..."
                highlights.append(highlight)
                
                if len(highlights) >= 3:
                    break
        
        return highlights
    
    async def delete(self, doc_id: str):
        """Delete a document from the store"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.execute("DELETE FROM documents_fts WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        
        self.index.remove(doc_id)
    
    def get_stats(self) -> dict:
        """Get store statistics"""
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        conn.close()
        
        return {
            "document_count": count,
            "embedding_dimension": self.embedding.dimension,
            "storage_path": str(self.storage_path)
        }


class RAGContext:
    """
    High-level RAG context manager for the AI agent.
    Integrates vector store with conversation context.
    """
    
    def __init__(self, vector_store: VectorStore, max_context_tokens: int = 4000):
        self.store = vector_store
        self.max_context_tokens = max_context_tokens
        
    async def augment_prompt(
        self,
        user_query: str,
        system_prompt: str = "",
        k: int = 5
    ) -> str:
        """
        Augment a prompt with relevant context from the vector store.
        
        Returns the augmented system prompt with retrieved context.
        """
        results = await self.store.search(user_query, k=k)
        
        if not results:
            return system_prompt
        
        # Build context section
        context_parts = []
        total_chars = 0
        char_limit = self.max_context_tokens * 4  # Rough estimate
        
        for result in results:
            content = result.document.content
            if total_chars + len(content) > char_limit:
                break
            
            source = result.document.metadata.get("source", "Unknown")
            context_parts.append(f"[Source: {source}, Relevance: {result.score:.2f}]\n{content}")
            total_chars += len(content)
        
        if not context_parts:
            return system_prompt
        
        context_section = "\n\n---\n\n".join(context_parts)
        
        augmented = f"""{system_prompt}

## Relevant Context (Retrieved from Knowledge Base)

{context_section}

---

Use the above context to inform your response when relevant. If the context doesn't contain relevant information, rely on your general knowledge."""
        
        return augmented
    
    async def add_to_knowledge_base(
        self,
        content: str,
        source: str = "user_provided",
        metadata: dict = None
    ) -> list[str]:
        """Add content to the knowledge base"""
        meta = {"source": source, **(metadata or {})}
        return await self.store.add_text(content, metadata=meta)
    
    async def search_knowledge(self, query: str, k: int = 5) -> list[dict]:
        """Search the knowledge base"""
        results = await self.store.search(query, k=k)
        return [
            {
                "content": r.document.content,
                "score": r.score,
                "metadata": r.document.metadata,
                "highlights": r.highlights
            }
            for r in results
        ]
