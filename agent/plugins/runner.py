"""Plugin sandbox runner: execute plugin commands in a subprocess with
best-effort resource limits and manifest-based permission checks.

Notes:
- This is a best-effort sandbox on cross-platform systems. For strong
  isolation prefer container-based execution (set env `DOCKER_SANDBOX=1`).
"""
from pathlib import Path
import logging
import subprocess
import shlex
import os
import time
from typing import Optional

import psutil
from prometheus_client import Counter, Histogram

from .manifest import PluginManifest

logger = logging.getLogger(__name__)

# Metrics
PLUGIN_EXEC_TOTAL = Counter(
    "ai_os_plugin_exec_total", "Total plugin executions", ["plugin", "result"]
)
PLUGIN_EXEC_DURATION = Histogram(
    "ai_os_plugin_exec_duration_seconds", "Plugin execution duration seconds", ["plugin"]
)


def _find_plugin_dir(name: str) -> Optional[Path]:
    base = Path(__file__).parent
    # plugin module may be a single file <name>_runner.py or a package folder
    candidate_file = base / f"{name}_runner.py"
    candidate_dir = base / name
    if candidate_file.exists():
        return candidate_file.parent
    if candidate_dir.exists():
        return candidate_dir
    return None


def _load_manifest(plugin_dir: Path) -> PluginManifest:
    # allow plugin to ship `plugin.yaml` or `manifest.yaml`
    for name in ("plugin.yaml", "manifest.yaml", "plugin.yml", "manifest.yml"):
        f = plugin_dir / name
        if f.exists():
            import yaml

            data = yaml.safe_load(f.read_text()) or {}
            return PluginManifest(**data)
    # default manifest
    return PluginManifest()


def run_plugin_subprocess(name: str, args: list[str]) -> int:
    """Run plugin runner in a subprocess enforcing manifest limits.

    Returns subprocess exit code.
    """
    plugin_dir = _find_plugin_dir(name)
    manifest = _load_manifest(plugin_dir if plugin_dir else Path(__file__).parent)

    # Build command. Support package-style plugins (directory named `name`) or
    # legacy module-style runners named `<name>_runner.py`.
    if plugin_dir and plugin_dir.is_dir() and plugin_dir.name == name:
        module_to_run = f"agent.plugins.{name}"
    else:
        module_to_run = f"agent.plugins.{name}_runner"

    cmd = ["python", "-m", module_to_run] + args

    # Optionally support docker-based sandbox if requested and available
    use_docker = os.environ.get("DOCKER_SANDBOX") == "1"
    if use_docker:
        # best-effort: requires docker and a small python image
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none" if not manifest.network else "bridge",
            "--memory",
            f"{manifest.max_memory_mb}m",
            "python:3.11-slim",
            "python",
            "-m",
            module_to_run,
        ] + args
        try:
            logger.info("Running plugin in docker sandbox: %s", shlex.join(docker_cmd))
            start = time.time()
            res = subprocess.run(docker_cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            PLUGIN_EXEC_TOTAL.labels(plugin=name, result=str(res.returncode)).inc()
            PLUGIN_EXEC_DURATION.labels(plugin=name).observe(time.time() - start)
            return res.returncode
        except FileNotFoundError:
            logger.warning("docker not found, falling back to local subprocess")

    # Run as a local subprocess with resource monitoring
    env = {"PYTHONUNBUFFERED": "1"}
    # minimal environment
    safe_env = {k: v for k, v in os.environ.items() if k in ("PATH", "PYTHONPATH", "PYTHONHOME")}
    safe_env.update(env)

    logger.info("Running plugin subprocess: %s", shlex.join(cmd))
    start = time.time()
    proc = subprocess.Popen(cmd, env=safe_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p = None
    try:
        p = psutil.Process(proc.pid)
    except Exception:
        p = None

    try:
        timeout = manifest.max_cpu_seconds
        check_interval = 0.1
        while True:
            if proc.poll() is not None:
                break
            if (time.time() - start) > timeout:
                proc.kill()
                logger.warning("Plugin %s exceeded timeout (%s)s and was killed", name, timeout)
                PLUGIN_EXEC_TOTAL.labels(plugin=name, result="killed_timeout").inc()
                PLUGIN_EXEC_DURATION.labels(plugin=name).observe(time.time() - start)
                return 124
            if p is not None:
                try:
                    rss = p.memory_info().rss // (1024 * 1024)
                    if rss > manifest.max_memory_mb:
                        proc.kill()
                        logger.warning("Plugin %s exceeded memory limit (%sMB) and was killed", name, manifest.max_memory_mb)
                        PLUGIN_EXEC_TOTAL.labels(plugin=name, result="killed_memory").inc()
                        PLUGIN_EXEC_DURATION.labels(plugin=name).observe(time.time() - start)
                        return 125
                except psutil.NoSuchProcess:
                    break
            time.sleep(check_interval)

        stdout, stderr = proc.communicate(timeout=1)
        rc = proc.returncode
        PLUGIN_EXEC_TOTAL.labels(plugin=name, result=str(rc)).inc()
        PLUGIN_EXEC_DURATION.labels(plugin=name).observe(time.time() - start)
        if rc != 0:
            logger.error("Plugin %s exited %s: %s", name, rc, stderr.decode(errors='ignore'))
        else:
            logger.debug("Plugin %s output: %s", name, stdout.decode(errors='ignore'))
        return rc
    except subprocess.TimeoutExpired:
        proc.kill()
        PLUGIN_EXEC_TOTAL.labels(plugin=name, result="killed_timeout").inc()
        PLUGIN_EXEC_DURATION.labels(plugin=name).observe(time.time() - start)
        return 124
    except Exception:
        logger.exception("Plugin subprocess failed")
        PLUGIN_EXEC_TOTAL.labels(plugin=name, result="error").inc()
        PLUGIN_EXEC_DURATION.labels(plugin=name).observe(time.time() - start)
        try:
            proc.kill()
        except Exception:
            pass
        return 1
