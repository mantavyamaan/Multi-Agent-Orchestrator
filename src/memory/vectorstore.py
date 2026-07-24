"""Vector database integration for Semantic Memory."""
import os
import chromadb
from typing import List

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db")

class SemanticMemory:
    def __init__(self, collection_name: str = "agent_memory"):
        self.client = chromadb.PersistentClient(path=_DB_PATH)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def save(self, memory_id: str, text: str, metadata: dict = None):
        """Save a new memory."""
        self.collection.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[memory_id]
        )

    def search(self, query: str, n_results: int = 3) -> List[str]:
        """Retrieve relevant past memories."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        if results['documents'] and results['documents'][0]:
            return results['documents'][0]
        return []

semantic_memory = SemanticMemory()
