#!/usr/bin/env python3
import sys, os
sys.path.insert(0, '/home/user/.local/lib/python3.7/site-packages')
os.chdir('/home/user/trainer-marketplace')
os.environ['PYTHONPATH'] = '/home/user/.local/lib/python3.7/site-packages'

import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=8000, reload=False, workers=1, log_level='warning')
