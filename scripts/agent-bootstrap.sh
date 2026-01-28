#!/usr/bin/env bash
set -e

echo "Bootstrapping agent environment..."

# -------- Backend --------
if [ -d "backend" ]; then
  cd backend

  if [ ! -d "venv" ]; then
    echo "Creating Python venv"
    python3 -m venv venv
  fi

  echo "Activating venv"
  source venv/bin/activate

  echo "Installing backend dependencies"
  pip install -r requirements.txt

  cd ..
fi

# -------- Frontend --------
if [ -d "frontend" ]; then
  cd frontend

  if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies"
    npm install
  fi

  cd ..
fi

echo "Agent environment ready"
