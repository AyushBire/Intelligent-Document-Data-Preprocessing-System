"""Isolate API tests from local credentials, presentation access and real databases."""
import os

os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_idps.db"
os.environ["PRELOAD_MODELS"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["PRESENTATION_AUTH_ENABLED"] = "false"
