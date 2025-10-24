# Temporary compatibility mechanism between Poetry and uv.
# While waiting for full adoption of PEP 751 (the standardized lock format `pylock.toml`),
# we maintain separate lock files for each tool (`poetry.lock` and `uv.lock`)
# and also generate a unified `pylock.toml` for future interoperability.
# This ensures that developers can use either Poetry or uv seamlessly in the same project.

deps:
	uv sync

deps-poetry:
	poetry install

lock-all:
	uv lock
	poetry lock
	uv export -o pylock.toml
	git add pylock.toml

.PHONY: deps deps-poetry lock-all
