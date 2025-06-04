#!/bin/bash
uvicorn app-frontend.main:app --host 0.0.0.0 --port 8000 --reload