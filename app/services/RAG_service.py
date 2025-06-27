from app.db.RAG_db import log_session_interaction, get_recent_memory

def query_context_from_memory(query: str, session_id: str):
    try:
        memory_docs = get_recent_memory(session_id, 3)
        if not memory_docs:
            return ""
        return "\n---\n".join(doc for doc in memory_docs if doc)
    except Exception as e:
        print(f"Error in query_context_from_memory: {e}")
        return ""
