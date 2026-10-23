import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_health(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/",
                                        timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"server on :{port} did not become healthy")


class Server:
    def __init__(self, db_path: str):
        self.port = free_port()
        self.db = db_path
        self.proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/mcp"

    def start(self) -> "Server":
        env = dict(os.environ, CREW_MEMORY_DB=self.db)
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "mcp_server.py"),
             "--port", str(self.port)],
            cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_health(self.port)
        return self

    def stop(self) -> None:
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None


@pytest.fixture()
def server(tmp_path):
    srv = Server(str(tmp_path / "test_memory.db")).start()
    yield srv
    srv.stop()
