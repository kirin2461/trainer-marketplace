#!/usr/bin/env python3
import sys, os
sys.path.insert(0, '/home/user/.local/lib/python3.7/site-packages')
os.chdir('/home/user/trainer-marketplace')

# Daemonize
pid = os.fork()
if pid > 0:
    sys.exit(0)
os.setsid()
os.umask(0)
pid = os.fork()
if pid > 0:
    sys.exit(0)

# Redirect stdout/stderr
import uvicorn
sys.stdout = open('/tmp/uvicorn.log', 'a')
sys.stderr = sys.stdout

uvicorn.run('app.main:app', host='127.0.0.1', port=8000, log_level='info')

