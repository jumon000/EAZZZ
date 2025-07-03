
from app.db.database import engine, Base
from app.db.models import ChatMessage  

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully.")