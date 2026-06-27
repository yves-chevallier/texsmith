include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
BASE_PDF := $(OUTPUT_DIR)/book.pdf
PDF := $(OUTPUT_DIR)/book$(ENGINE_SUFFIX).pdf

# Typst output -> build/typst/book.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/book.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): book.md book.bib | $(OUTPUT_DIR)
	$(TEXSMITH) book.md book.bib -o$(OUTPUT_DIR) --build -tbook -abibliography_style=numeric $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

$(TYPST_PDF): book.md book.bib | $(TYPST_DIR)
	$(TEXSMITH) book.md book.bib -o$(TYPST_DIR) -tbook --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
