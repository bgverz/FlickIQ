from __future__ import annotations
import os
import sys
import re
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

def _redact(url: str | None) -> str:
    if not url:
        return "<empty>"
    url = re.sub(r":([^:@/]+)@", r":******@", url)                
    url = re.sub(r"(password=)([^&]+)", r"\1******", url)          
    return url

def main() -> int:
    load_dotenv()
    from config.settings import DATABASE_URL

    print("Connecting with:")
    print("  ", _redact(DATABASE_URL))

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            print("SELECT 1 ->", conn.execute(text("SELECT 1")).scalar_one())
            try:
                ssl = conn.execute(text("SHOW ssl")).scalar_one_or_none()
                if ssl is not None:
                    print("SSL:", ssl)
            except Exception:
                pass
            version = conn.execute(text("SHOW server_version")).scalar_one()
            print("Postgres version:", version)
        print("✅ Connection OK")
        return 0
    except OperationalError as e:
        print("❌ OperationalError\n", str(e))
        return 1
    except Exception as e:
        print("❌ Unexpected error:", repr(e))
        return 1

if __name__ == "__main__":
    sys.exit(main())
