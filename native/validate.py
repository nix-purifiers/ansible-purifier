import re
import sys
import yaml

data = yaml.safe_load(open(sys.argv[1]))
if not isinstance(data, dict) or set(data) - {"collections"}:
    raise ValueError(
        "Use collection-only native requirements; roles need a separate provider"
    )
collections = data.get("collections", [])
if not isinstance(collections, list):
    raise ValueError("Native collections must be a list")
for collection in collections:
    item = {"name": collection} if isinstance(collection, str) else collection
    if not isinstance(item, dict) or set(item) - {"name", "version", "type", "source"}:
        raise ValueError("Unsupported native collection requirement")
    if item.get("type", "galaxy") != "galaxy" or item.get(
        "source", "https://galaxy.ansible.com"
    ) not in (
        "https://galaxy.ansible.com",
        "https://galaxy.ansible.com/",
        "https://galaxy.ansible.com/api/",
    ):
        raise ValueError("The initial integration supports public Galaxy collections")
    if not isinstance(item.get("name"), str) or not re.fullmatch(
        r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+(?::[^/\s]+)?", item["name"]
    ):
        raise ValueError("Use a native namespace.collection requirement")
print(len(collections))
