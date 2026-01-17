"""
Script to create the initial database migration
Run this script to generate the first migration file
"""

import subprocess
import sys
import os

def create_migration():
    try:
        # Change to the project directory
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

        # Create initial migration
        result = subprocess.run([
            sys.executable, "-m", "alembic", "revision", "--autogenerate",
            "-m", "initial migration with all models"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Initial migration created successfully!")
            print(result.stdout)
        else:
            print("❌ Error creating migration:")
            print(result.stderr)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_migration()
