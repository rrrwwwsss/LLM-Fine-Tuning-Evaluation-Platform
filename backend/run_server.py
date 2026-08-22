import uvicorn
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 生产模式：nohup python run_server.py --prod
prod_mode = "--prod" in sys.argv or "--production" in sys.argv
reload_enabled = not prod_mode

uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=18080,
    log_level="info",
    reload=reload_enabled
)
