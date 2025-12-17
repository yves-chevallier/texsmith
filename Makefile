PRE_CMD := uv run

examples:
	cd examples && $(PRE_CMD) make all

artifacts:
	./scripts/refresh_cli_help.sh

docs: artifacts
	TEXSMITH_BUILD=1 $(PRE_CMD) mkdocs build

lint:
	$(PRE_CMD) ruff format .
	$(PRE_CMD) ruff check .
	$(PRE_CMD) ruff format .

clean:
	$(RM) -rf build press site

.PHONY: examples artifacts docs clean lint
