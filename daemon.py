#!/usr/bin/env python3
import sys, os, subprocess
sys.path.insert(0, '/home/user/.local/lib/python3.7/site-packages')
os.chdir('/home/user/trainer-marketplace')
import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=8000, log_level='info')
