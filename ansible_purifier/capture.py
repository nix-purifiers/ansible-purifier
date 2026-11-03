import base64
import json
import os
from pathlib import Path
import tempfile

from .common import environment, inputs, load, relative, run


def capture(root, companion, update=False, requirements=None, extra=()):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = json.loads(companion.read_text()) if companion.exists() else {}
    requirements = requirements or previous.get("requirements", "requirements.yml")
    extra = list(extra or previous.get("extraInputs", []))
    selection = inputs(root, requirements, extra)
    sdk = Path(os.environ["ANSIBLE_PURIFIER_SDK"])
    with tempfile.TemporaryDirectory(prefix="ansible-capture-") as temporary:
        state = Path(temporary)
        env = environment(root, state)
        record = state / "selected.json"
        record.write_text("{}")
        env["ANSIBLE_PURIFIER_CAPTURE"] = str(record)
        count = int(
            run(
                [
                    os.environ["ANSIBLE_PURIFIER_PYTHON"],
                    str(sdk / "lib/ansible-purifier/native/validate.py"),
                    str(root / requirements),
                ],
                env=env,
            )
        )
        if count:
            run(
                [
                    os.environ["ANSIBLE_PURIFIER_PYTHON"],
                    str(sdk / "lib/ansible-purifier/native/capture.py"),
                    "collection",
                    "download",
                    "--requirements-file",
                    str(root / requirements),
                    "--download-path",
                    str(state / "downloads"),
                ],
                cwd=root,
                env=env,
            )
        selected = json.loads(record.read_text())
        entries = []
        for name, item in sorted(selected.items()):
            if not relative(name) or len(name.split(".")) != 2:
                raise ValueError("Invalid native collection identity")
            entries.append(
                {
                    "path": "artifacts/" + name + ".tar.gz",
                    "url": item["url"],
                    "mirrors": [],
                    "hash": "sha256-"
                    + base64.b64encode(bytes.fromhex(item["sha256"])).decode(),
                    "ansible": {"name": name, "version": item["version"]},
                }
            )
        data = dict(
            version=1,
            purifier="ansible",
            sdk=os.environ["ANSIBLE_PURIFIER_SDK_VERSION"],
            requirements=requirements,
            extraInputs=extra,
            inputs=selection,
            entries=entries,
        )
        if inputs(root, requirements, extra) != selection:
            raise ValueError("Selection inputs changed during native resolution")
        companion.parent.mkdir(parents=True, exist_ok=True)
        staged = companion.with_name(companion.name + ".tmp")
        staged.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        staged.replace(companion)
