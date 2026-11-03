import hashlib
import json
import os
from pathlib import Path
import subprocess


def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    return result.stdout


def relative(name):
    return (
        isinstance(name, str)
        and bool(name)
        and not Path(name).is_absolute()
        and ".." not in Path(name).parts
        and "\n" not in name
        and "\r" not in name
    )


def inputs(root, requirements, extra):
    names = sorted(
        set(
            [requirements, *extra]
            + (["ansible.cfg"] if (root / "ansible.cfg").exists() else [])
        )
    )
    if not all(relative(n) and (root / n).is_file() for n in names):
        raise ValueError("Selection inputs must be project files")
    return {
        n: {"sha256": hashlib.sha256((root / n).read_bytes()).hexdigest()}
        for n in names
    }


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "ansible":
        raise ValueError("Unsupported Ansible lock")
    if data["sdk"] != os.environ["ANSIBLE_PURIFIER_SDK_VERSION"]:
        raise ValueError("Ansible SDK changed; update the lock")
    if inputs(root, data["requirements"], data["extraInputs"]) != data["inputs"]:
        raise ValueError("Selection inputs changed; update the lock")
    return data


def environment(root, state):
    env = dict(os.environ)
    env.pop("ANSIBLE_PURIFIER_FROZEN", None)
    state.mkdir(parents=True, exist_ok=True)
    config = root / "ansible.cfg"
    if not config.exists():
        config = state / "ansible.cfg"
        config.write_text("[defaults]\n")
    env["ANSIBLE_CONFIG"] = str(config)
    env["ANSIBLE_HOME"] = str(state)
    env["ANSIBLE_LOCAL_TEMP"] = str(state / "tmp")
    env["ANSIBLE_COLLECTIONS_SCAN_SYS_PATH"] = "false"
    return env
