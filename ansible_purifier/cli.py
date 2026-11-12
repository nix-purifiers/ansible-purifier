import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from .capture import capture
from .runtime import prepare
from .common import run


def locate(project=None, companion=None):
    root = Path(
        project or os.environ.get("ANSIBLE_PURIFIER_PROJECT", Path.cwd())
    ).resolve()
    external = companion or os.environ.get("ANSIBLE_PURIFIER_LOCK")
    if external:
        return root, Path(external).resolve()
    if project or os.environ.get("ANSIBLE_PURIFIER_PROJECT"):
        return root, root / "ansible-purifier.lock.json"
    for directory in [root, *root.parents]:
        if (directory / "ansible-purifier.lock.json").exists():
            return directory, directory / "ansible-purifier.lock.json"
    return root, root / "ansible-purifier.lock.json"


def native(name, args, root, companion):
    if not companion.exists():
        print(
            "ansible-purifier: no lockfile; using ordinary impure " + name,
            file=sys.stderr,
        )
        env = dict(os.environ)
        env.pop("ANSIBLE_PURIFIER_FROZEN", None)
        return subprocess.call(
            [str(Path(os.environ["ANSIBLE_PURIFIER_ORIGINAL"]) / "bin" / name), *args],
            env=env,
        )
    if name == "ansible-galaxy" and ("install" in args or "download" in args):
        raise ValueError(
            "Dependencies are provided by the lock; use ansible-purifier lock --update to change them"
        )
    env = prepare(root, companion)
    return subprocess.call(
        [str(Path(os.environ["ANSIBLE_PURIFIER_TOOL"]) / "bin" / name), *args], env=env
    )


def main_impl():
    args = sys.argv[1:]
    if args and args[0].startswith("--native="):
        root, companion = locate()
        return native(args[0].split("=", 1)[1], args[1:], root, companion)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--requirements")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--tag", default="v0.1.0")
    opts, rest = parser.parse_known_args(args)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    root, companion = locate(opts.project, opts.lock)
    if opts.action == "lock":
        capture(root, companion, opts.update, opts.requirements, opts.input)
    elif opts.action == "prefetch":
        prepare(root, companion)
    elif opts.action == "exec":
        if not rest:
            raise ValueError("Pass a command after --")
        return subprocess.call(rest, env=prepare(root, companion))
    else:
        prepare(root, companion)
        expression = (
            "import "
            + json.dumps(
                os.environ["ANSIBLE_PURIFIER_SDK"]
                + "/lib/ansible-purifier/pkgs/build-ansible-project/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";version="
            + json.dumps(opts.tag)
            + ";}"
        )
        output = Path(
            run(
                [
                    "nix",
                    "build",
                    "--impure",
                    "--no-link",
                    "--print-out-paths",
                    "--expr",
                    expression,
                ]
            ).strip()
        )
        if opts.action == "bundle":
            print(output / "ansible-project.tar.gz")
        else:
            subprocess.run(
                [
                    os.environ["ANSIBLE_PURIFIER_GH"],
                    "release",
                    "upload",
                    opts.tag,
                    str(output / "ansible-project.tar.gz"),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )
    return 0


def main():
    try:
        raise SystemExit(main_impl())
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print("ansible-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
