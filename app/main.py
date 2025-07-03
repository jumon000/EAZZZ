from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # For the /token endpoint
from pydantic import BaseModel, EmailStr
from typing import List
from app.autogen_config.planner_config import EcommerceAssistant
from app.db.RAG_db import clear_session
import os
from dotenv import load_dotenv

# --- New Imports ---
from sqlalchemy.orm import Session
from app.db.database import get_db, engine
from app.db import models
from app.services import history_service, user_service, auth_services
from datetime import timedelta

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="E-Commerce Autogen Agent")
load_dotenv() 

assistant = EcommerceAssistant()

# --- Pydantic Models for API requests/responses ---

# User registration request
class UserCreate(BaseModel):
    email: EmailStr # Automatic email validation
    password: str

# User response (without password)
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    class Config:
        orm_mode = True

# Token response
class Token(BaseModel):
    access_token: str
    token_type: str

# Query request no longer needs user_id, it comes from the token
class QueryRequest(BaseModel):
    query: str
    session_id: str

class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    user_id: int # user_id is now an integer
    role: str
    content: str
    created_at: str

class SessionResponse(BaseModel):
    session_id: str
    last_updated: str
    title: str

# --- Authentication Endpoints (Public) ---

@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Creates a new user account."""
    db_user = user_service.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return user_service.create_user(db=db, email=user.email, password=user.password)

@app.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Logs in a user to get a JWT token."""
    user = user_service.get_user_by_email(db, email=form_data.username) # OAuth2 form uses 'username' field for email
    if not user or not auth_services.verify_password(form_data.password, user.hashed_password.value):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_services.create_access_token(
        data={"sub": user.email}
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Protected Endpoints ---

@app.post("/query")
async def handle_query(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_services.get_current_user) # Dependency to protect the route
):
    """
    Accepts a user query, saves it, processes it, and saves the response.
    The user's identity is determined by the provided Bearer token.
    """
    history_service.save_chat_message(
        db=db, user_id=current_user.id.value, session_id=request.session_id, role="user", content=request.query
    )
    response_content = assistant.process_query(query=request.query, session_id=request.session_id)
    history_service.save_chat_message(
        db=db, user_id=str(current_user.id), session_id=request.session_id, role="assistant", content=response_content
    )
    return {"session_id": request.session_id, "response": response_content}

@app.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_services.get_current_user)
):
    """
    Retrieves a list of all chat sessions for the authenticated user.
    """
    sessions = history_service.get_sessions_by_user(db, user_id=str(current_user.id))
    return sessions

@app.get("/chat-history/{session_id}", response_model=List[ChatMessageResponse])
async def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_services.get_current_user) # Protected
):
    """
    Retrieves the full message history for a specific session,
    ensuring the session belongs to the authenticated user.
    """
    history = history_service.get_history_by_session(db, session_id)
    # Security check: Ensure the user is not trying to access another user's chat
    if isinstance(history, list) and len(history) > 0:
        # Ensure user_id is an int for comparison
        message_user_id = history[0].user_id
        if str(message_user_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this chat history")
    return [message.to_dict() for message in history]

@app.delete("/clear-session/{session_id}")
async def clear_session_route(
    session_id: str,
    current_user: models.User = Depends(auth_services.get_current_user) # Protected
):
    """Clears the RAG context for a session. The user must be authenticated."""
    clear_session(session_id)
    return {"message": f"RAG context for Session {session_id} cleared."}

@app.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: models.User = Depends(auth_services.get_current_user)):
    """A simple endpoint to check the current authenticated user."""
    return current_user