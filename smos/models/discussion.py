from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from smos.core.database import Base

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    memory_node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Reaction(Base):
    __tablename__ = "reactions"
    id = Column(Integer, primary_key=True, index=True)
    memory_node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    emoji = Column(String)
