from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

class RepositoryError(RuntimeError):
    pass

def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RepositoryError(f"Arquivo não encontrado: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RepositoryError(f"JSON inválido em {path}: {exc}") from exc

def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise

def load_dataset(data_dir: Path = DATA_DIR) -> dict[str, dict[str, Any]]:
    return {
        "organs": load_json(data_dir / "organs.json"),
        "contests": load_json(data_dir / "contests.json"),
        "positions": load_json(data_dir / "positions.json"),
        "alerts": load_json(data_dir / "alert_config.json"),
    }
