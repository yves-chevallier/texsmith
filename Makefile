PRE_CMD := uv run
# The TMark specification lives in the tmark repository (single source of truth).
TMARK_SPEC ?= ../tmark/spec/tmark.md

examples:
	cd examples && $(PRE_CMD) make all

artifacts:
	./scripts/refresh_cli_help.sh

docs: artifacts
	TEXSMITH_BUILD=1 $(PRE_CMD) mkdocs build

# The same mkdocs.yml through Zensical: the web lowering runs as the
# 'texsmith.site.web' Markdown extension, and no PDF is built. Zensical
# clears the site directory and caches rendered pages, so the stylesheet and
# the snippet previews are made first, as sources under docs/.
site-assets: artifacts
	$(PRE_CMD) texsmith site assets mkdocs.yml

# The book hangs off no hook Zensical has, so it is a command of its own.
docs-zensical: site-assets
	$(PRE_CMD) zensical build -f mkdocs.yml
	$(PRE_CMD) texsmith site build mkdocs.yml

serve-zensical: site-assets
	$(PRE_CMD) zensical serve -f mkdocs.yml

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

.PHONY: examples artifacts docs site-assets docs-zensical serve-zensical spec clean lint ir-fixtures
