from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]

dotenv_path = BASE_DIR / ".env"

print("Looking for:", dotenv_path)
print("Exists:", dotenv_path.exists())

load_dotenv(dotenv_path) 

print("API KEY:", os.getenv("GROQ_API_KEY"))