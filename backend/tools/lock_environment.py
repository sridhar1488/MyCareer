"""Snapshot resolved runtime/test dependency closures from the validated environment."""

import tomllib
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def closure(requirements):
    resolved, visited = {}, set()
    pending = [Requirement(r) for r in requirements]
    while pending:
        requirement = pending.pop()
        key = (canonicalize_name(requirement.name), tuple(sorted(requirement.extras)))
        if key in visited:
            continue
        visited.add(key)
        distribution = metadata.distribution(requirement.name)
        resolved[key[0]] = f"{distribution.metadata['Name']}=={distribution.version}"
        for raw in distribution.requires or []:
            dependency = Requirement(raw)
            if not dependency.marker or any(
                dependency.marker.evaluate({"extra": extra}) for extra in (requirement.extras or {""})
            ):
                pending.append(dependency)
    return resolved


runtime = closure(project["dependencies"])
testing = closure(project["optional-dependencies"]["test"])
header = "# Resolved and tested on Python 3.12 / Windows; see docs/07-running.md.\n"
(ROOT / "requirements.lock").write_text(
    header + "\n".join(runtime[k] for k in sorted(runtime)) + "\n", encoding="utf-8"
)
(ROOT / "requirements-dev.lock").write_text(
    header
    + "-r requirements.lock\n"
    + "\n".join(testing[k] for k in sorted(testing) if k not in runtime)
    + "\n",
    encoding="utf-8",
)
print(
    f"Locked {len(runtime)} runtime and {len(testing.keys() - runtime.keys())} additional test dependencies."
)
