import uvicorn
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
uvicorn.run('main:app', host='0.0.0.0', port=18080, log_level='info')
