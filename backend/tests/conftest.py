import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./agentcart-test.db")
os.environ.setdefault("PAYPAL_CLIENT_ID", "")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "")
os.environ.setdefault("GEMINI_API_KEY", "")
