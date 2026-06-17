"""اجرای محلی برای توسعه:  python run.py  (یا: uvicorn app.main:app --reload)"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
