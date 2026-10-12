import os
import subprocess
import sys

repo = r"c:\Users\Asus\Desktop\Parth 2D"
os.chdir(repo)
python_exe = r"C:\Users\Asus\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\python.exe"
cmd = [python_exe, '-m', 'uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', '8000']
print('Starting backend with:', cmd)
proc = subprocess.Popen(cmd, cwd=repo)
print('PID:', proc.pid)
proc.wait(timeout=5)
