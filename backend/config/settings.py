from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    user = os.getenv("DB_USER", "postgres")
    pwd = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "postgres")
    ssl = os.getenv("DB_SSLMODE", "require")
    DATABASE_URL = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{name}?sslmode={ssl}"

# debug
print(f"Final DATABASE_URL: {DATABASE_URL}")