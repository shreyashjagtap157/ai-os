import importlib
from types import SimpleNamespace


def test_load_config_uses_keyring(monkeypatch, tmp_path):
    # create a minimal config file without secrets
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("agent:\n  allowed_root: '.'\n")

    # monkeypatch keyring.get_password
    fake = {}

    def fake_get_password(service, name):
        return {"api_key": "from-keyring", "session_hmac_key": "hmac-key"}.get(name)

    monkeypatch.setitem(__import__("builtins").__dict__, "__name__", "builtins")
    # ensure keyring is available in module import path
    import keyring as _kr

    monkeypatch.setattr(_kr, "get_password", fake_get_password, raising=True)

    # import the config loader and call load_config
    cfg_mod = importlib.import_module("agent.config")
    cfg = cfg_mod.load_config(str(cfg_path))
    assert cfg.api_key == "from-keyring"
    assert cfg.session_hmac_key == "hmac-key"
