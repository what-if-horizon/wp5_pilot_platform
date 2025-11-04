import json
import importlib.util
from pathlib import Path


def _load_participant_module():
    fn = Path(__file__).resolve().parents[1] / "utils" / "participant_tokens.py"
    spec = importlib.util.spec_from_file_location("participant_tokens", str(fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_find_and_mark_token(tmp_path):
    mod = _load_participant_module()

    backend_dir = tmp_path / "backend"
    config_dir = backend_dir / "config"
    logs_dir = backend_dir / "logs"
    config_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    pt = {"groups": {"Tx1": ["token-1", "token-2"]}}
    write_json(config_dir / "participant_tokens.json", pt)

    # Point module to tmp backend dir
    mod.BASE_DIR = backend_dir
    mod.TOKENS_PATH = backend_dir / "config" / "participant_tokens.json"
    mod.USED_TOKENS_LOG = backend_dir / "logs" / "used_tokens.jsonl"

    # token should be found
    g = mod.find_group_for_token("token-1")
    assert g == "Tx1"

    # mark token used
    mod.mark_token_used("token-1", session_id="s1", group="Tx1")

    # now find_group_for_token should return None (single-use)
    g2 = mod.find_group_for_token("token-1")
    assert g2 is None
