#!/bin/bash
source .venv/bin/activate
export PYTHONPATH=$PWD
python -m uvicorn api.main:app --reload --port 8000
