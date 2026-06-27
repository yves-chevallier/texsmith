include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
BASE_PDF := $(OUTPUT_DIR)/diagrams.pdf
PDF := $(OUTPUT_DIR)/diagrams$(ENGINE_SUFFIX).pdf

# Typst output -> build/typst/diagrams.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/diagrams.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): diagrams.md | pgcd.drawio $(OUTPUT_DIR)
	$(TEXSMITH) diagrams.md -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

$(TYPST_PDF): diagrams.md | pgcd.drawio $(TYPST_DIR)
	$(TEXSMITH) diagrams.md -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
