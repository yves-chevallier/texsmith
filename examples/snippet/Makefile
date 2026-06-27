include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/snippet$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/snippet.pdf

# Typst output -> build/typst/snippet.pdf (engine-agnostic, native compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/snippet.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): docs/index.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	mv $(OUTPUT_DIR)/index.pdf $(PDF)
	$(call copy_artifact,$@)

$(TYPST_PDF): docs/index.md | $(TYPST_DIR)
	$(TEXSMITH) $< -o$(TYPST_DIR) -tarticle --format typst --build
	mv $(TYPST_DIR)/index.pdf $(TYPST_PDF)
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
