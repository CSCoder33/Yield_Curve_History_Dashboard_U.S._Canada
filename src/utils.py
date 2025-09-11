import os
import json
import yaml
from datetime import datetime, timezone


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def save_json(obj, path: str) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def stamp_last_updated(readme_path: str, when: str) -> None:
    # Replace or insert a line starting with "Last updated:" in README
    if not os.path.exists(readme_path):
        return
    with open(readme_path, "r") as f:
        lines = f.readlines()
    out = []
    replaced = False
    for line in lines:
        if line.strip().lower().startswith("last updated:"):
            out.append(f"Last updated: {when}\n")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"\nLast updated: {when}\n")
    with open(readme_path, "w") as f:
        f.writelines(out)

