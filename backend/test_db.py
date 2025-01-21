import asyncio
from app.db.database import check_db_connection, DATABASE_URL, SessionLocal
import uvicorn
import requests
import time
import sys
from multiprocessing import Process
from datetime import datetime
import uuid
from app.db.models import HistoryRecordDB

def run_server():
    """Run the FastAPI server for testing."""
    import os
    os.environ["GITHUB_TOKEN"] = "ghp_dummy"  # Set dummy token to prevent GitHub service initialization
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="error")

def create_test_record():
    """Create a test record in the database."""
    db = SessionLocal()
    try:
        test_record = HistoryRecordDB(
            aid=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            repository="test/repo",
            commit_hash="abc123",
            analysis_result={"test": "data"},
            status="completed",
            notes="Test record"
        )
        db.add(test_record)
        db.commit()
        return test_record.aid
    finally:
        db.close()

def main():
    # Test database connection
    print(f"\nTesting database connection...")
    print("Testing database connection with configured environment variables...")
    connection_result = check_db_connection()
    print(f"Database connection test: {'SUCCESS' if connection_result else 'FAILED'}")

    if not connection_result:
        print("Database connection failed. Exiting...")
        sys.exit(1)

    # Create test record
    print("\nCreating test record...")
    test_aid = create_test_record()
    print(f"Created test record with aid: {test_aid}")

    # Start server in a separate process
    print("\nStarting server for endpoint tests...")
    server = Process(target=run_server)
    server.start()
    
    # Wait for server to start
    time.sleep(2)
    
    try:
        # Test health check endpoint
        print("\nTesting health check endpoint...")
        health_response = requests.get("http://localhost:8000/healthz")
        print(f"Health check status code: {health_response.status_code}")
        print(f"Health check response: {health_response.json()}")
        
        # Test /api/history endpoint
        print("\nTesting /api/history endpoint...")
        history_response = requests.get("http://localhost:8000/api/history")
        print(f"History status code: {history_response.status_code}")
        history_data = history_response.json()
        print(f"History records count: {len(history_data)}")
        
        # Test /api/history/{aid} endpoint
        print(f"\nTesting /api/history/{test_aid} endpoint...")
        record_response = requests.get(f"http://localhost:8000/api/history/{test_aid}")
        print(f"Record status code: {record_response.status_code}")
        if record_response.status_code == 200:
            record_data = record_response.json()
            print(f"Record data: {record_data}")
        
        # Test non-existent record
        print("\nTesting non-existent record...")
        fake_aid = str(uuid.uuid4())
        not_found_response = requests.get(f"http://localhost:8000/api/history/{fake_aid}")
        print(f"Not found status code: {not_found_response.status_code}")
        
        # Verify all tests passed
        all_passed = (
            health_response.status_code == 200 and
            history_response.status_code == 200 and
            record_response.status_code == 200 and
            not_found_response.status_code == 404
        )
        
        if all_passed:
            print("\nAll tests passed successfully!")
            sys.exit(0)
        else:
            print("\nSome tests failed!")
            sys.exit(1)
    
    finally:
        # Clean up
        server.terminate()
        server.join()

if __name__ == "__main__":
    main()
