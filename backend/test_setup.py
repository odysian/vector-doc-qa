#!/usr/bin/env python3
"""
Test script to verify backend setup.

This script:
1. Checks if all required packages are installed
2. Verifies database connection
3. Initializes database (creates tables)
4. Queries the database to confirm tables exist

Run: python test_setup.py
"""

import sys
from pathlib import Path

print("\n" + "=" * 60)
print("🧪 TESTING BACKEND SETUP")
print("=" * 60 + "\n")

# ============================================================================
# 1. Check Package Imports
# ============================================================================
print("📦 Step 1: Checking package imports...")

try:
    import fastapi

    print("  ✅ fastapi")
except ImportError as e:
    print(f"  ❌ fastapi - {e}")
    sys.exit(1)

try:
    import sqlalchemy

    print("  ✅ sqlalchemy")
except ImportError as e:
    print(f"  ❌ sqlalchemy - {e}")
    sys.exit(1)

try:
    import pgvector

    print("  ✅ pgvector")
except ImportError as e:
    print(f"  ❌ pgvector - {e}")
    sys.exit(1)

try:
    import pydantic

    print("  ✅ pydantic")
except ImportError as e:
    print(f"  ❌ pydantic - {e}")
    sys.exit(1)

try:
    import pdfplumber

    print("  ✅ pdfplumber")
except ImportError as e:
    print(f"  ❌ pdfplumber - {e}")
    sys.exit(1)

print("\n✅ All required packages installed!\n")

# ============================================================================
# 2. Check Configuration
# ============================================================================
print("⚙️  Step 2: Checking configuration...")

try:
    from app.config import settings

    print(f"  ✅ Config loaded")
    print(f"  📊 Database URL: {settings.database_url}")
    print(f"  📁 Upload dir: {settings.upload_dir}")
    print(f"  📏 Max file size: {settings.max_file_size / 1024 / 1024:.1f}MB")
except Exception as e:
    print(f"  ❌ Config error: {e}")
    sys.exit(1)

print()

# ============================================================================
# 3. Initialize Database
# ============================================================================
print("🗄️  Step 3: Initializing database...")

try:
    from app.database import SessionLocal, engine, init_db
    from app.models.base import Chunk, Document, DocumentStatus

    # Initialize database (creates tables)
    init_db()
    print("  ✅ Database initialized")

except Exception as e:
    print(f"  ❌ Database initialization failed: {e}")
    print("\n⚠️  Make sure PostgreSQL is running:")
    print("     docker-compose up -d")
    sys.exit(1)

print()

# ============================================================================
# 4. Test Database Connection
# ============================================================================
print("🔌 Step 4: Testing database connection...")

try:
    from sqlalchemy import text

    # Create a session
    db = SessionLocal()

    # Test query
    result = db.execute(text("SELECT 1"))
    db.close()

    print("  ✅ Database connection successful")

except Exception as e:
    print(f"  ❌ Database connection failed: {e}")
    print("\n⚠️  Check if Docker container is running:")
    print("     docker ps | grep pgvector")
    sys.exit(1)

print()

# ============================================================================
# 5. Verify Tables Exist
# ============================================================================
print("📋 Step 5: Verifying tables...")

try:
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    required_tables = ["documents", "chunks"]

    for table in required_tables:
        if table in tables:
            print(f"  ✅ Table '{table}' exists")

            # Get columns
            columns = [col["name"] for col in inspector.get_columns(table)]
            print(f"     Columns: {', '.join(columns)}")
        else:
            print(f"  ❌ Table '{table}' missing")
            sys.exit(1)

except Exception as e:
    print(f"  ❌ Table verification failed: {e}")
    sys.exit(1)

print()

# ============================================================================
# 6. Check pgvector Extension
# ============================================================================
print("🔍 Step 6: Checking pgvector extension...")

try:
    db = SessionLocal()
    result = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
    if result.fetchone():
        print("  ✅ pgvector extension enabled")
    else:
        print("  ⚠️  pgvector extension not found")
        print("     Should be auto-enabled by init_db()")
    db.close()
except Exception as e:
    print(f"  ⚠️  Could not check pgvector: {e}")

print()

# ============================================================================
# 7. Verify Upload Directory
# ============================================================================
print("📁 Step 7: Checking upload directory...")

try:
    upload_dir = settings.get_upload_path()

    if upload_dir.exists():
        print(f"  ✅ Upload directory exists: {upload_dir}")
    else:
        print(f"  ℹ️  Creating upload directory: {upload_dir}")
        upload_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Upload directory created")

except Exception as e:
    print(f"  ❌ Upload directory check failed: {e}")
    sys.exit(1)

print()

# ============================================================================
# SUCCESS
# ============================================================================
print("=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\n🚀 Your backend is ready!")
print("\nNext steps:")
print("  1. Start the server: uvicorn app.main:app --reload")
print("  2. Visit docs: http://localhost:8000/docs")
print("  3. Test health endpoint: curl http://localhost:8000/health")
print()
