#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/user/.local/lib/python3.7/site-packages')

# Pre-import to verify
import passlib
import fastapi
import sqlalchemy
import jinja2
print("All imports OK, starting server...", file=sys.stderr)

import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=8000, log_level='info')
