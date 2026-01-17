"""
Script to run database migrations
This will apply all pending migrations to the database
"""

import subprocess
import sys
import os

def run_migrations():
    try:
        # Change to the project directory
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

        # Run migrations
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Migrations applied successfully!")
            print(result.stdout)
        else:
            print("❌ Error running migrations:")
            print(result.stderr)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_migrations()
