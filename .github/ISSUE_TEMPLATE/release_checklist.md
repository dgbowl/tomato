---
name: Release Checklist
about: Release checklist for minor and major tomato releases.
title: Release checklist for `tomato-vX.Y`
labels: ''
assignees: ''

---

## Release checklist

### Preparing a release candidate:
- [ ] tests pass on `main` branch
- [ ] `dgbowl-schemas` released and updated in `pyproject.toml`
- [ ] `__latest_payload__` in `src/tomato/ketchup/__init__.py` updated
- [ ] `docs/version.rst` updated 

### Preparing a full release
- [ ] `docs/version.rst` release date updated

### After release
- [ ] pypi packages built and uploaded
- [ ] docs built and deployed
