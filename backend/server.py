import os
import uvicorn
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def run():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "1") not in ("0", "false", "False")
    # Import path points to the FastAPI app inside the backend package
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()


