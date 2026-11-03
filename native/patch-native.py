from pathlib import Path

p = Path("lib/ansible/utils/collection_loader/_collection_finder.py")
s = p.read_text()
needle = "self._n_cached_collection_paths = paths = self._n_playbook_paths + self._n_configured_paths"
replacement = "self._n_cached_collection_paths = paths = ([] if os.environ.get('ANSIBLE_PURIFIER_FROZEN') else self._n_playbook_paths) + self._n_configured_paths"
assert s.count(needle) == 1
p.write_text(s.replace(needle, replacement))
