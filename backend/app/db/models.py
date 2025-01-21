from sqlalchemy import Column, String, DateTime, Text, JSON, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class HistoryRecordDB(Base):
    """SQLAlchemy model for storing analysis history records."""
    __tablename__ = "history_records"

    # Primary key and record identification
    aid = Column(String(36), primary_key=True, comment="Unique identifier for the analysis record")
    
    # Core analysis metadata
    timestamp = Column(DateTime, nullable=False, comment="Timestamp when the analysis was performed")
    repository = Column(String(255), nullable=False, comment="GitHub repository name (owner/repo)")
    commit_hash = Column(String(40), nullable=False, comment="Git commit hash")
    
    # Analysis data
    analysis_result = Column(JSON, nullable=False, comment="Complete analysis results in JSON format")
    status = Column(String(50), nullable=False, default="completed", comment="Analysis status")
    notes = Column(Text, nullable=True, comment="Optional notes or feedback")
    
    # Record management
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="Record creation timestamp")
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp"
    )

    def __repr__(self):
        """String representation of the record."""
        return f"<HistoryRecord(aid={self.aid}, repository={self.repository}, commit={self.commit_hash})>"

    def to_dict(self):
        """Convert record to dictionary format."""
        return {
            "aid": self.aid,
            "timestamp": self.timestamp.isoformat(),
            "repository": self.repository,
            "commit": self.commit_hash,
            "analysisResult": self.analysis_result,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
