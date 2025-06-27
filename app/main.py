from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional
from app.autogen_config.planner_config import EcommerceAssistant
from app.db.RAG_db import clear_session
import os
from dotenv import load_dotenv


app = FastAPI(title="E-Commerce Autogen Agent")

print("DEBUG: OPENAI_API_KEY =", os.getenv("GEMINI_API_KEY"))

load_dotenv() 

assistant = EcommerceAssistant()

class QueryRequest(BaseModel):
    query: str
    session_id: str

@app.post("/query")
async def handle_query(request: QueryRequest):
    """
    Accepts a user query and processes it via Autogen planner/executor using RAG memory.
    """
    response = assistant.process_query(query=request.query, session_id=request.session_id)
    return {"session_id": request.session_id, "response": response}

# @app.get("/execution-history")
# async def get_exec_history():
#     return assistant.get_execution_stats()

@app.delete("/clear-session/{session_id}")
async def clear_session_route(session_id: str):
    clear_session(session_id)
    return {"message": f"Session {session_id} cleared."}