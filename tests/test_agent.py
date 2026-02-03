import pytest
from agent.system_api import SystemAPI
from agent.agent import parse_command, CommandRegistry
from pathlib import Path


def test_parse_command():
    assert parse_command("ls /tmp") == ("ls", ["/tmp"])
    assert parse_command("  ") == ("", [])
    assert parse_command("echo hello world") == ("echo", ["hello", "world"])


def test_system_api_list_files(tmp_path: Path):
    (tmp_path / "foo").write_text("x")
    (tmp_path / "bar").write_text("y")
    api = SystemAPI(allowed_root=tmp_path)
    files = api.list_files(tmp_path)
    assert "foo" in files
    assert "bar" in files


def test_system_api_list_files_not_directory(tmp_path: Path):
    (tmp_path / "file.txt").write_text("content")
    api = SystemAPI(allowed_root=tmp_path)
    with pytest.raises(NotADirectoryError):
        api.list_files(tmp_path / "file.txt")


def test_system_api_list_files_permission(tmp_path: Path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    api = SystemAPI(allowed_root=tmp_path)
    # Trying to access outside allowed_root should fail
    with pytest.raises(PermissionError):
        api.list_files("/etc")


def test_command_registry_exit(capsys):
    api = SystemAPI(allowed_root=Path.cwd())
    registry = CommandRegistry(api)
    should_continue = registry.execute("exit", [])
    assert should_continue is False
    captured = capsys.readouterr()
    # Should not print anything, just exit


def test_command_registry_help(capsys):
    api = SystemAPI(allowed_root=Path.cwd())
    registry = CommandRegistry(api)
    should_continue = registry.execute("help", [])
    assert should_continue is True
    captured = capsys.readouterr()
    assert "Available commands" in captured.out
    assert "exit" in captured.out


def test_command_registry_echo(capsys):
    api = SystemAPI(allowed_root=Path.cwd())
    registry = CommandRegistry(api)
    should_continue = registry.execute("echo", ["hello", "world"])
    assert should_continue is True
    captured = capsys.readouterr()
    assert "hello world" in captured.out


def test_command_registry_unknown_command(capsys):
    api = SystemAPI(allowed_root=Path.cwd())
    registry = CommandRegistry(api)
    should_continue = registry.execute("unknown_cmd", [])
    assert should_continue is True
    captured = capsys.readouterr()
    assert "Unknown command" in captured.out


def test_plugin_registration(capsys, tmp_path, monkeypatch):
    # Ensure plugin discovery finds our sample plugin and registers p-echo
    api = SystemAPI(allowed_root=Path.cwd())
    registry = CommandRegistry(api)
    from agent.plugins import load_plugin
    mod = load_plugin('agent.plugins.sample_echo')
    assert mod is not None
    mod.register(registry)
    assert 'p-echo' in registry.commands
    registry.execute('p-echo', ['hello', 'plugin'])
    captured = capsys.readouterr()
    assert 'hello plugin' in captured.out
