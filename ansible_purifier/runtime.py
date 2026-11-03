import hashlib
import json
import os
from pathlib import Path

from .common import environment, load, run


def prepare(root, companion):
    data = load(root, companion)
    generation = hashlib.sha256(
        companion.read_bytes() + os.environ["ANSIBLE_PURIFIER_SDK"].encode()
    ).hexdigest()[:20]
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    state = cache_home / "ansible-purifier" / key / generation
    state.mkdir(parents=True, exist_ok=True)
    expression = (
        "import "
        + json.dumps(
            os.environ["ANSIBLE_PURIFIER_SDK"] + "/lib/ansible-purifier/nix/realize.nix"
        )
        + " {root="
        + json.dumps(str(root))
        + ";lockFile="
        + json.dumps(str(companion))
        + ";sdk="
        + json.dumps(os.environ["ANSIBLE_PURIFIER_SDK"])
        + ";}"
    )
    profile = Path(
        run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--out-link",
                str(state / "environment-profile"),
                "--print-out-paths",
            ]
        ).strip()
    )
    manifest = json.loads(
        (Path(json.loads(profile.read_text())["output"]) / "manifest.json").read_text()
    )
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared Ansible SDK differs from the lock")
    env = environment(root, state / "session")
    env["ANSIBLE_COLLECTIONS_PATH"] = manifest["collections"]
    env["ANSIBLE_PURIFIER_FROZEN"] = "1"
    env["ANSIBLE_COLLECTIONS_SCAN_SYS_PATH"] = "false"
    env["PATH"] = (
        str(Path(os.environ["ANSIBLE_PURIFIER_SDK"]) / "bin") + os.pathsep + env["PATH"]
    )
    return env
