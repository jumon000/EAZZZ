from sqlalchemy.orm import Session
from sqlalchemy import desc, func, distinct
from app.db.models import ChatMessage
from typing import List, Dict

def save_chat_message(db: Session, user_id: str, session_id: str, role: str, content: str):
    """Saves a single chat message to the database."""
    db_message = ChatMessage(
        user_id=user_id,
        session_id=session_id,
        role=role,
        content=content
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def get_history_by_session(db: Session, session_id: str) -> List[ChatMessage]:
    """Retrieves all messages for a given session, ordered by creation time."""
    return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()

def get_sessions_by_user(db: Session, user_id: str) -> List[Dict]:
    """Retrieves all unique sessions for a user, ordered by the most recent message."""
    latest_message_subquery = db.query(
        ChatMessage.session_id,
        func.max(ChatMessage.created_at).label("latest_created_at")
    ).filter(ChatMessage.user_id == user_id).group_by(ChatMessage.session_id).subquery()

    first_message_subquery = db.query(
        ChatMessage.session_id,
        func.min(ChatMessage.created_at).label("first_created_at")
    ).filter(ChatMessage.user_id == user_id).group_by(ChatMessage.session_id).subquery()

    first_message = db.query(
        ChatMessage.session_id,
        ChatMessage.content.label("title")
    ).join(
        first_message_subquery,
        (ChatMessage.session_id == first_message_subquery.c.session_id) &
        (ChatMessage.created_at == first_message_subquery.c.first_created_at)
    ).subquery()
    
    sessions = db.query(
        latest_message_subquery.c.session_id,
        latest_message_subquery.c.latest_created_at,
        first_message.c.title
    ).join(
        first_message,
        latest_message_subquery.c.session_id == first_message.c.session_id
    ).order_by(desc(latest_message_subquery.c.latest_created_at)).all()
    
    return [
        {"session_id": s.session_id, "last_updated": s.latest_created_at.isoformat(), "title": s.title}
        for s in sessions
    ]