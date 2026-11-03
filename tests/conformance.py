import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
import threading

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)


with tempfile.TemporaryDirectory(prefix="ansible proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(repo / "examples/minimal", root)
    env = dict(
        os.environ,
        XDG_CACHE_HOME=str(temp / "xdg"),
        ANSIBLE_HOME=str(temp / "ambient"),
        ANSIBLE_COLLECTIONS_PATH=str(temp / "poison"),
        ANSIBLE_COLLECTIONS_SCAN_SYS_PATH="true",
    )

    def call(directory, name, *args, success=True, extra=None):
        result = subprocess.run(
            [sdk / "bin" / name, *args],
            cwd=directory,
            env=dict(env, **(extra or {})),
            text=True,
            capture_output=True,
            timeout=300,
        )
        assert (result.returncode == 0) == success, result
        return result

    companion = root / "ansible-purifier.lock.json"
    before = companion.read_bytes()
    assert (
        "42.0"
        in call(root, "ansible-playbook", "-i", "localhost,", "playbook.yml").stdout
    )
    playbook = root / "playbook.yml"
    original = playbook.read_text()
    playbook.write_text(original.replace("42", "43"))
    assert (
        "43.0"
        in call(root, "ansible-playbook", "-i", "localhost,", "playbook.yml").stdout
    )
    playbook.write_text(original)
    assert (
        "42.0"
        in call(root, "ansible-playbook", "-i", "localhost,", "playbook.yml").stdout
    )
    assert before == companion.read_bytes()
    poison = (
        root
        / "collections/ansible_collections/community/general/plugins/filter/to_seconds.py"
    )
    poison.parent.mkdir(parents=True)
    poison.write_text(
        "class FilterModule:\n def filters(self): return {'to_seconds': lambda value: 999}\n"
    )
    assert (
        "42.0"
        in call(root, "ansible-playbook", "-i", "localhost,", "playbook.yml").stdout
    )
    shutil.rmtree(root / "collections")
    result = call(root, "ansible-doc", "-t", "filter", "community.general.to_seconds")
    assert "/nix/store/" in result.stdout
    call(
        root,
        "ansible-galaxy",
        "collection",
        "install",
        "community.general",
        success=False,
    )
    subdir = root / "subdir"
    subdir.mkdir()
    assert (
        "42.0"
        in call(
            subdir, "ansible-playbook", "-i", "localhost,", "../playbook.yml"
        ).stdout
    )
    profiles = list((temp / "xdg/ansible-purifier").glob("*/*/environment-profile"))
    assert len(profiles) == 1
    profile = profiles[0]
    profile_data = json.loads(profile.read_text())
    closure = subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profile.resolve())], text=True
    )
    assert str(sdk) in closure
    manifest = json.loads((Path(profile_data["output"]) / "manifest.json").read_text())
    collections = Path(manifest["collections"])
    assert not (collections.stat().st_mode & 0o222)
    # Ordinary native Ansible can consume the prepared collection layout.
    ordinary = dict(
        env,
        ANSIBLE_COLLECTIONS_PATH=str(collections),
        ANSIBLE_COLLECTIONS_SCAN_SYS_PATH="false",
        ANSIBLE_HOME=str(temp / "ordinary"),
    )
    expression = (
        "let f=builtins.getFlake "
        + json.dumps(str(repo))
        + ";p=import f.inputs.nixpkgs {};in p.python3.withPackages (ps: [ps.ansible-core])"
    )
    original_sdk = Path(
        subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--no-link",
                "--print-out-paths",
            ],
            text=True,
        ).strip()
    )
    consumer = temp / "consumer"
    consumer.mkdir()
    (consumer / "playbook.yml").write_text(original)
    result = subprocess.run(
        [original_sdk / "bin/ansible-playbook", "-i", "localhost,", "playbook.yml"],
        cwd=consumer,
        env=ordinary,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and "42.0" in result.stdout, result

    # Root task networking remains available; no global socket/git/curl blockers.
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"42")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    playbook.write_text(
        "- hosts: localhost\n  connection: local\n  gather_facts: false\n  vars:\n    ansible_python_interpreter: '{{ ansible_playbook_python }}'\n    ansible_remote_tmp: '{{ lookup(\"ansible.builtin.env\", \"ANSIBLE_HOME\") }}/remote'\n  tasks:\n    - ansible.builtin.uri:\n        url: http://127.0.0.1:"
        + str(server.server_port)
        + "/\n        return_content: true\n      register: response\n    - ansible.builtin.assert:\n        that: response.content == '42'\n"
    )
    try:
        call(root, "ansible-playbook", "-i", "localhost,", "playbook.yml")
    finally:
        server.shutdown()
        server.server_close()
    playbook.write_text(original)
    external = temp / "companion.json"
    companion.rename(external)
    external_env = {
        "ANSIBLE_PURIFIER_PROJECT": str(root),
        "ANSIBLE_PURIFIER_LOCK": str(external),
    }
    assert (
        "42.0"
        in call(
            root,
            "ansible-playbook",
            "-i",
            "localhost,",
            "playbook.yml",
            extra=external_env,
        ).stdout
    )
    archive = Path(
        call(root, "ansible-purifier", "bundle", "--lock", str(external)).stdout.strip()
    )
    assert archive.is_file()
    published = temp / "published-native-consumer"
    published.mkdir()
    with tarfile.open(archive) as source_archive:
        source_archive.extractall(published, filter="data")
    result = subprocess.run(
        [original_sdk / "bin/ansible-playbook", "-i", "localhost,", "playbook.yml"],
        cwd=published,
        env=ordinary,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and "42.0" in result.stdout, result
    fake_gh = temp / "fake-gh"
    fake_gh.write_text(
        "#!/usr/bin/env python3\nimport pathlib,sys\np=pathlib.Path(sys.argv[4]);pathlib.Path(__file__).with_suffix('.uploaded').write_bytes(p.read_bytes())\n"
    )
    fake_gh.chmod(0o755)
    call(
        root,
        "ansible-purifier",
        "publish",
        "--lock",
        str(external),
        extra={"ANSIBLE_PURIFIER_GH": str(fake_gh)},
    )
    assert fake_gh.with_suffix(".uploaded").read_bytes() == archive.read_bytes()
    requirements = root / "requirements.yml"
    requirements.write_text(requirements.read_text() + "\n# selection changed\n")
    call(
        root,
        "ansible-playbook",
        "-i",
        "localhost,",
        "playbook.yml",
        extra=external_env,
        success=False,
    )
    fallback = temp / "fallback"
    fallback.mkdir()
    assert "ordinary impure" in call(fallback, "ansible", "--version").stderr
    fake_sdk = temp / "fake-sdk"
    (fake_sdk / "bin").mkdir(parents=True)
    fake = fake_sdk / "bin/ansible"
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    fake.chmod(0o755)
    direct = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/ansible-purifier"),
        ANSIBLE_PURIFIER_ORIGINAL=str(fake_sdk),
    )
    result = subprocess.run(
        ["python3", "-m", "ansible_purifier.cli", "--native=ansible"],
        cwd=fallback,
        env=direct,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result
print(
    "Native Ansible source edits, readonly collections, lookup isolation, root networking, ordinary consumer, publication and fallback passed"
)
