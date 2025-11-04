import json
import importlib.util
from pathlib import Path


def _load_participant_module():
    """Load the participant_tokens module by file path so tests don't depend on sys.path."""
    fn = Path(__file__).resolve().parents[1] / "utils" / "participant_tokens.py"
    spec = importlib.util.spec_from_file_location("participant_tokens", str(fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_validate_against_experiments_pass(tmp_path):
    mod = _load_participant_module()

    backend_dir = tmp_path / "backend"
    config_dir = backend_dir / "config"
    config_dir.mkdir(parents=True)

    exp = {"groups": {"TxA": {"prompt_template": "A"}, "TxB": {"prompt_template": "B"}}}
    write_json(config_dir / "experimental_settings.json", exp)

    pt = {"groups": {"TxA": ["t-a-1"], "TxB": ["t-b-1"]}}
    write_json(config_dir / "participant_tokens.json", pt)

    # point module to our tmp backend dir
    mod.BASE_DIR = backend_dir
    # ensure module path constants point to our tmp files (TOKENS_PATH computed at import)
    mod.TOKENS_PATH = backend_dir / "config" / "participant_tokens.json"
    mod.USED_TOKENS_LOG = backend_dir / "logs" / "used_tokens.jsonl"

    # Should not raise
    mod.validate_against_experiments(exp)


def test_validate_against_experiments_missing_group(tmp_path):
    mod = _load_participant_module()

    backend_dir = tmp_path / "backend"
    config_dir = backend_dir / "config"
    config_dir.mkdir(parents=True)

    exp = {"groups": {"TxA": {"prompt_template": "A"}}}
    write_json(config_dir / "experimental_settings.json", exp)

    # participant tokens reference unknown group TxMissing
    pt = {"groups": {"TxMissing": ["t-x-1"]}}
    write_json(config_dir / "participant_tokens.json", pt)

    mod.BASE_DIR = backend_dir
    mod.TOKENS_PATH = backend_dir / "config" / "participant_tokens.json"
    mod.USED_TOKENS_LOG = backend_dir / "logs" / "used_tokens.jsonl"

    try:
        mod.validate_against_experiments(exp)
        raised = False
    except RuntimeError:
        raised = True

    assert raised
