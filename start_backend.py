import os
import sys
import uvicorn

if __name__ == "__main__":
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, repo_dir)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

