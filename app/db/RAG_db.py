from uuid import uuid4
import time
import chromadb
from chromadb.config import Settings

from chromadb import PersistentClient

chroma_client = PersistentClient(path="./chroma_db")


collection = chroma_client.get_or_create_collection(name="user_session_memory")

def log_session_interaction(user_query: str, agent_response: str, session_id: str):
    collection = chroma_client.get_or_create_collection(name=f"user_session_{session_id}")
    interaction_id = str(uuid4())
    timestamp = time.time()

    collection.add(
        documents=[f"User: {user_query}\nAgent: {agent_response}"],
        metadatas=[{
            "session_id": session_id,
            "query": user_query,
            "response": agent_response,
            "timestamp": timestamp
        }],
        ids=[interaction_id]
    )

def get_recent_memory(session_id: str, n=5):
    collection = chroma_client.get_or_create_collection(name=f"user_session_{session_id}")
    
    results = collection.get(include=["documents", "metadatas"])
    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []

    if len(documents) != len(metadatas):
        min_len = min(len(documents), len(metadatas))
        documents = documents[:min_len]
        metadatas = metadatas[:min_len]
    
    if not documents:
        return []

    combined = list(zip(documents, metadatas))
    def get_timestamp(metadata):
        if not metadata:
            return 0.0
        timestamp = metadata.get("timestamp")
        if timestamp is None:
            return 0.0
        try:
            return float(timestamp)
        except (ValueError, TypeError):
            return 0.0
    
    combined.sort(key=lambda x: get_timestamp(x[1]))

    return [doc for doc, _ in combined[-n:]]

def clear_session(session_id: str):
    chroma_client.delete_collection(name=f"user_session_{session_id}")

