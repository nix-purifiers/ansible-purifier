"""Observe native resolution and verified artifact acquisition; retain its solver."""

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from ansible.galaxy.collection.concrete_artifact_manager import ConcreteArtifactsManager

original = ConcreteArtifactsManager.get_galaxy_artifact_path
records = {}


def capture(self, collection):
    path = original(self, collection)
    metadata, api = self._galaxy_collection_cache[collection]
    url = urlsplit(metadata.download_url)
    if (
        url.scheme != "https"
        or url.hostname != "galaxy.ansible.com"
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("The initial integration supports public Galaxy artifacts")
    digest = hashlib.sha256(Path(os.fsdecode(path)).read_bytes()).hexdigest()
    if digest != metadata.artifact_sha256:
        raise ValueError("Native Galaxy artifact checksum differs")
    records[collection.fqcn] = dict(
        version=collection.ver, url=metadata.download_url, sha256=digest
    )
    Path(os.environ["ANSIBLE_PURIFIER_CAPTURE"]).write_text(
        json.dumps(records, sort_keys=True, indent=2) + "\n"
    )
    return path


ConcreteArtifactsManager.get_galaxy_artifact_path = capture
from ansible.cli.galaxy import main

main()
