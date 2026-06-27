include ../common.mk

# LaTeX output (default engine, e.g. tectonic) -> build/<engine>/cheese[-engine].pdf
OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/cheese$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/cheese.pdf

# Typst output -> build/typst/cheese.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/cheese.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): cheese.md cheese.bib | $(OUTPUT_DIR)
	$(TEXSMITH) $^ -o$(OUTPUT_DIR) -tarticle --build $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

$(TYPST_PDF): cheese.md cheese.bib | $(TYPST_DIR)
	$(TEXSMITH) $^ -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
