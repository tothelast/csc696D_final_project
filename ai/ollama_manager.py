"""Manage the lifecycle of a bundled Ollama process."""

import logging
import os
import platform
import subprocess
import time

import requests

logger = logging.getLogger(__name__)

# Try system Ollama (11434) first, fall back to bundled on 11435
_SYSTEM_PORT = 11434
_BUNDLED_PORT = 11435
_HEALTH_TIMEOUT = 30
_MODEL_NAME = "qwen3.5:latest"


class OllamaManager:
    """Start, monitor, and stop a bundled Ollama server process."""

    def __init__(self):
        self.port = _SYSTEM_PORT
        self.base_url = f"http://localhost:{self.port}"
        self._process: subprocess.Popen | None = None

    def start(self) -> bool:
        # Check if system Ollama is already running (e.g. systemd service)
        if self.is_healthy():
            logger.info("Ollama already running on port %d", self.port)
            return self._model_available()

        # Try bundled port
        self.port = _BUNDLED_PORT
        self.base_url = f"http://localhost:{self.port}"
        if self.is_healthy():
            logger.info("Ollama already running on port %d", self.port)
            return self._model_available()

        binary = self._find_binary()
        if not binary:
            logger.error("Ollama binary not found")
            return False

        env = os.environ.copy()
        env["OLLAMA_HOST"] = f"0.0.0.0:{self.port}"

        models_dir = self._find_models_dir()
        if models_dir:
            env["OLLAMA_MODELS"] = models_dir

        try:
            self._process = subprocess.Popen(
                [binary, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            logger.error("Failed to start Ollama: %s", exc)
            return False

        if not self._wait_healthy():
            logger.error("Ollama did not become healthy within %ds", _HEALTH_TIMEOUT)
            self.stop()
            return False

        if not self._model_available():
            logger.error("Model %s is not available", _MODEL_NAME)
            self.stop()
            return False

        logger.info("Ollama ready on port %d with model %s", self.port, _MODEL_NAME)
        return True

    def stop(self):
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            logger.info("Ollama process stopped")

    def is_healthy(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/version", timeout=2)
            return r.status_code == 200
        except requests.ConnectionError:
            return False

    def _wait_healthy(self) -> bool:
        deadline = time.time() + _HEALTH_TIMEOUT
        while time.time() < deadline:
            if self.is_healthy():
                return True
            time.sleep(0.5)
        return False

    def _model_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code != 200:
                return False
            models = r.json().get("models", [])
            return any(_MODEL_NAME in m.get("name", "") for m in models)
        except requests.ConnectionError:
            return False

    def _find_binary(self) -> str | None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        system = platform.system().lower()

        if system == "windows":
            bundled = os.path.join(project_root, "ollama", "windows", "ollama.exe")
        else:
            bundled = os.path.join(project_root, "ollama", "linux", "ollama")

        if os.path.isfile(bundled):
            return bundled

        import shutil
        return shutil.which("ollama")

    def _find_models_dir(self) -> str | None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.join(project_root, "ollama", "models")
        if os.path.isdir(models_dir):
            return models_dir
        return None
