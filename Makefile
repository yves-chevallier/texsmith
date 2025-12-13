examples:
	cd examples && uv run make all

artifacts:
	./scripts/refresh_cli_help.sh

docs: artifacts
	TEXSMITH_BUILD=1 uv run mkdocs build

clean:
	$(RM) -rf build press site

.PHONY: examples artifacts docs clean
