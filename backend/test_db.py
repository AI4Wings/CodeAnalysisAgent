import asyncio
from app.db.database import check_db_connection, DATABASE_URL
import uvicorn
import requests
import time
import sys
from multiprocessing import Process

def run_server():
    """Run the FastAPI server for testing."""
    import os
    os.environ["GITHUB_TOKEN"] = "ghp_dummy"  # Set dummy token to prevent GitHub service initialization
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="error")

def main():
    # Test database connection
    print(f"\nTesting database connection...")
    print(f"Using DATABASE_URL: {DATABASE_URL}")
    connection_result = check_db_connection()
    print(f"Database connection test: {'SUCCESS' if connection_result else 'FAILED'}")

    if not connection_result:
        print("Database connection failed. Exiting...")
        sys.exit(1)

    # Start server in a separate process
    print("\nStarting server for health check test...")
    server = Process(target=run_server)
    server.start()
    
    # Wait for server to start
    time.sleep(2)
    
    try:
        # Test health check endpoint
        print("\nTesting health check endpoint...")
        response = requests.get("http://localhost:8000/healthz")
        print(f"Health check status code: {response.status_code}")
        print(f"Health check response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok" and data.get("database") == "ok":
                print("\nAll tests passed successfully!")
                sys.exit(0)
        
        print("\nHealth check test failed!")
        sys.exit(1)
    
    finally:
        # Clean up
        server.terminate()
        server.join()

if __name__ == "__main__":
    main()
