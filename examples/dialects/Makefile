include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
BASE_PDF := $(OUTPUT_DIR)/dialects.pdf
PDF := $(OUTPUT_DIR)/dialects$(ENGINE_SUFFIX).pdf

# Typst output -> build/typst/dialects.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/dialects.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): dialects.md | $(OUTPUT_DIR)
	$(TEXSMITH) dialects.md -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

$(TYPST_PDF): dialects.md | $(TYPST_DIR)
	$(TEXSMITH) dialects.md -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
