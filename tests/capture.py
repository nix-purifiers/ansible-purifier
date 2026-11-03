import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="ansible native capture ") as temporary:
    root = Path(temporary)
    shutil.copytree(repo / "examples/minimal", root, dirs_exist_ok=True)
    companion = root / "ansible-purifier.lock.json"
    expected = json.loads(companion.read_text())["entries"]
    companion.unlink()
    env = dict(os.environ, XDG_CACHE_HOME=str(root / "cache"))
    subprocess.run(
        [sdk / "bin/ansible-purifier", "lock"], cwd=root, env=env, check=True
    )
    captured = json.loads(companion.read_text())["entries"]
    assert next(
        e for e in captured if e["ansible"]["name"] == "community.general"
    ) == next(e for e in expected if e["ansible"]["name"] == "community.general")
    assert {e["ansible"]["name"] for e in captured} >= {
        "community.general",
        "community.library_inventory_filtering_v1",
    }
    assert {e["ansible"]["name"] for e in expected} == {
        "community.general",
        "community.library_inventory_filtering_v1",
    }
    before = companion.read_bytes()
    subprocess.run(
        [sdk / "bin/ansible-purifier", "lock"], cwd=root, env=env, check=True
    )
    assert companion.read_bytes() == before
    subprocess.run(
        [sdk / "bin/ansible-playbook", "-i", "localhost,", "playbook.yml"],
        cwd=root,
        env=env,
        check=True,
    )
    (root / "requirements.yml").write_text("collections: []\n")
    subprocess.run(
        [sdk / "bin/ansible-purifier", "lock", "--update"],
        cwd=root,
        env=env,
        check=True,
    )
    assert json.loads(companion.read_text())["entries"] == []
    subprocess.run(
        [sdk / "bin/ansible-purifier", "prefetch"], cwd=root, env=env, check=True
    )
print("Native Galaxy transitive capture, stable lock and empty dependency set passed")
