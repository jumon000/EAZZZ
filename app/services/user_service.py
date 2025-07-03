from sqlalchemy.orm import Session
from app.db import models
from app.services import auth_services
from pydantic import EmailStr

def get_user_by_email(db: Session, email: str) -> models.User:
    """Finds a user by their email address."""
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, email: EmailStr, password: str) -> models.User:
    """Creates a new user in the database."""
    hashed_password = auth_services.get_password_hash(password)
    db_user = models.User(email=email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user