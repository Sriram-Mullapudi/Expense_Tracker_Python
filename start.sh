#!/usr/bin/env bash
set -e

if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

pip install -r requirements.txt
python app.py
