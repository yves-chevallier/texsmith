PRE_CMD := uv run
# The TMark specification lives in the tmark repository (single source of truth).
TMARK_SPEC ?= ../tmark/spec/tmark.md

examples:
	cd examples && $(PRE_CMD) make all

artifacts:
	./scripts/refresh_cli_help.sh

docs: artifacts
	TEXSMITH_BUILD=1 $(PRE_CMD) mkdocs build

spec:
	$(PRE_CMD) texsmith $(TMARK_SPEC) -o build/spec --build

# The IR inputs of the pass tests (tests/passes/<pass>/<case>.in.json), parsed by the installed tmark wheel.
ir-fixtures:
	$(PRE_CMD) python scripts/refresh_pass_fixtures.py

lint:
	$(PRE_CMD) ruff format .
	$(PRE_CMD) ruff check .
	$(PRE_CMD) ruff format .

clean:
	$(RM) -rf build press site
	$(MAKE) -C examples clean

.PHONY: examples artifacts docs spec clean lint ir-fixtures
