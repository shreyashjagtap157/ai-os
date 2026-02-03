import importlib
from agent.plugins import runner


def test_heavy_plugin_memory_killed():
    # Request allocation larger than manifest max_memory_mb (50MB)
    rc = runner.run_plugin_subprocess("heavy_plugin", ["--alloc-mb", "200"])
    # Expect runner to kill process due to memory (125) in our implementation
    assert rc == 125
