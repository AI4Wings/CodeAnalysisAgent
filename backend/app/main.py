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

# Global storage for history records
history_records: Dict[str, Dict[str, Any]] = {}

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

class HistoryRecord(BaseModel):
    """Model for storing analysis history records"""
    aid: str
    timestamp: str
    repository: str
    commit: str
    analysisResult: Dict[str, Any]
    status: str = "completed"
    notes: Optional[str] = None

class CommitAnalysisRequest(BaseModel):
    commit_url: str

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/api/history")
async def list_history_records():
    """List all history records"""
    return list(history_records.values())

@app.get("/api/history/{aid}")
async def get_history_record(aid: str):
    """Get a specific history record by aid"""
    if aid not in history_records:
        raise HTTPException(status_code=404, detail="History record not found")
    return history_records[aid]

@app.post("/api/history/{aid}/reanalyze")
async def reanalyze_history_record(aid: str):
    """Re-analyze a specific commit from history"""
    if aid not in history_records:
        raise HTTPException(status_code=404, detail="History record not found")
    
    existing_record = history_records[aid]
    
    try:
        # Get commit changes from GitHub
        changes = github_service.get_commit_changes(
            f"https://github.com/{existing_record['repository']}/commit/{existing_record['commit']}"
        )
        
        if not changes.get("files"):
            raise HTTPException(status_code=400, detail="No files found in commit")
        
        # Re-analyze changes
        analysis_results = await asyncio.wait_for(
            analysis_service.analyze_changes(changes),
            timeout=60.0
        )
        
        # Create new history record for re-analysis
        new_aid = str(uuid.uuid4())
        new_record = HistoryRecord(
            aid=new_aid,
            timestamp=datetime.utcnow().isoformat(),
            repository=existing_record["repository"],
            commit=existing_record["commit"],
            analysisResult=analysis_results,
            status="completed",
            notes=f"Re-analysis of {aid}"
        )
        
        history_records[new_aid] = new_record.dict()
        return new_record
        
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Analysis timed out. Please try again with a smaller commit."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_commit(request: CommitAnalysisRequest):
    try:
        # Get commit changes from GitHub
        changes = github_service.get_commit_changes(request.commit_url)
        if not changes.get("files"):
            raise HTTPException(status_code=400, detail="No files found in commit")
            
        # Add timeout for analysis
        try:
            # Analyze changes using LangChain with timeout
            analysis_results = await asyncio.wait_for(
                analysis_service.analyze_changes(changes),
                timeout=60.0  # 60 second timeout
            )
            
            # Create history record
            aid = str(uuid.uuid4())
            history_record = HistoryRecord(
                aid=aid,
                timestamp=datetime.utcnow().isoformat(),
                repository=changes.get("repository", ""),
                commit=changes.get("commit", ""),
                analysisResult=analysis_results,
                status="completed"
            )
            history_records[aid] = history_record.dict()
            
            # Return analysis results with aid
            return {
                **analysis_results,
                "aid": aid
            }
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Analysis timed out. Please try again with a smaller commit."
            )
    except (ValueError, GitHubError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AnalysisError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
