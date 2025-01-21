from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import json
from typing import List, Dict, Any, Optional
import asyncio
import uuid
from datetime import datetime

from app.services.github_service import GitHubService, GitHubError
from app.services.analysis_service import AnalysisService, AnalysisError

# Import database dependencies
from app.db.database import get_db
from app.db.models import HistoryRecordDB
from sqlalchemy.orm import Session
from fastapi import Depends

app = FastAPI(
    title="Code Analysis Agent API",
    description="API for analyzing code changes in GitHub commits with focus on Android compatibility",
    version="1.0.0"
)

@app.get("/")
@app.head("/")
async def root():
    """Redirect to frontend application"""
    return RedirectResponse(
        url="https://code-analysis-app-antgsu28.devinapps.com",
        status_code=307
    )

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize services
github_service = GitHubService()
analysis_service = AnalysisService()

# Request model for commit analysis

class CommitAnalysisRequest(BaseModel):
    commit_url: str

@app.get("/healthz")
async def healthz():
    """Health check endpoint that also verifies database connection."""
    from app.db.database import check_db_connection
    
    db_status = "ok" if check_db_connection() else "error"
    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/history")
async def list_history_records(db: Session = Depends(get_db)):
    """List all history records"""
    try:
        records = db.query(HistoryRecordDB).order_by(HistoryRecordDB.timestamp.desc()).all()
        return [record.to_dict() for record in records]
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.get("/api/history/{aid}")
async def get_history_record(aid: str, db: Session = Depends(get_db)):
    """Get a specific history record by aid"""
    try:
        record = db.query(HistoryRecordDB).filter(HistoryRecordDB.aid == aid).first()
        if not record:
            raise HTTPException(status_code=404, detail="History record not found")
        return record.to_dict()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

@app.post("/api/history/{aid}/reanalyze")
async def reanalyze_history_record(aid: str, db: Session = Depends(get_db)):
    """Re-analyze a specific commit from history"""
    try:
        # Get existing record from database
        existing_record = db.query(HistoryRecordDB).filter(HistoryRecordDB.aid == aid).first()
        if not existing_record:
            raise HTTPException(status_code=404, detail="History record not found")
        
        # Get commit changes from GitHub
        changes = github_service.get_commit_changes(
            f"https://github.com/{existing_record.repository}/commit/{existing_record.commit_hash}"
        )
        
        if not changes.get("files"):
            raise HTTPException(status_code=400, detail="No files found in commit")
        
        try:
            # Re-analyze changes with timeout
            analysis_results = await asyncio.wait_for(
                analysis_service.analyze_changes(changes),
                timeout=60.0
            )
            
            # Create new history record for re-analysis
            new_aid = str(uuid.uuid4())
            new_record = HistoryRecordDB(
                aid=new_aid,
                timestamp=datetime.utcnow(),
                repository=existing_record.repository,
                commit_hash=existing_record.commit_hash,
                analysis_result=analysis_results,
                status="completed",
                notes=f"Re-analysis of {aid}"
            )
            
            db.add(new_record)
            db.commit()
            return new_record.to_dict()
        except asyncio.TimeoutError:
            db.rollback()
            raise HTTPException(
                status_code=504,
                detail="Analysis timed out. Please try again with a smaller commit."
            )
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
        
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Analysis timed out. Please try again with a smaller commit."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_commit(request: CommitAnalysisRequest, db: Session = Depends(get_db)):
    """Analyze a commit and store results in database."""
    try:
        # Get commit changes from GitHub
        changes = github_service.get_commit_changes(request.commit_url)
        if not changes.get("files"):
            raise HTTPException(status_code=400, detail="No files found in commit")
            
        try:
            # Analyze changes using LangChain with timeout
            analysis_results = await asyncio.wait_for(
                analysis_service.analyze_changes(changes),
                timeout=60.0  # 60 second timeout
            )
            
            # Create history record
            aid = str(uuid.uuid4())
            history_record = HistoryRecordDB(
                aid=aid,
                timestamp=datetime.utcnow(),
                repository=changes.get("repository", ""),
                commit_hash=changes.get("commit", ""),
                analysis_result=analysis_results,
                status="completed"
            )
            
            # Save to database
            db.add(history_record)
            db.commit()
            
            # Return analysis results with aid
            return {
                **analysis_results,
                "aid": aid
            }
        except asyncio.TimeoutError:
            db.rollback()
            raise HTTPException(
                status_code=504,
                detail="Analysis timed out. Please try again with a smaller commit."
            )
    except (ValueError, GitHubError) as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except AnalysisError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        db.close()
