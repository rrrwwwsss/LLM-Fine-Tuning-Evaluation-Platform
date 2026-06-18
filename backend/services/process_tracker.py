import os
import signal
import threading
import subprocess

_lock = threading.Lock()
_processes: list = []

def register(proc: subprocess.Popen) -> None:
    with _lock:
        _processes.append(proc)

def unregister(proc: subprocess.Popen) -> None:
    with _lock:
        try:
            _processes.remove(proc)
        except ValueError:
            pass

def kill_all() -> None:
    with _lock:
        for proc in _processes[:]:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    import time
                    time.sleep(0.5)
                    if proc.poll() is None:
                        proc.kill()
            except Exception:
                pass
        _processes.clear()