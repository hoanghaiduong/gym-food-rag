@echo off
echo "Dang kich hoat virtual environment..."
call myenv\Scripts\activate

echo "Khoi dong FastAPI voi Uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
