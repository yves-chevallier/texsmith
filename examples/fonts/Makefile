include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
BASE_PDF := $(OUTPUT_DIR)/fonts.pdf
PDF := $(OUTPUT_DIR)/fonts$(ENGINE_SUFFIX).pdf

# Typst output -> build/typst/fonts.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/fonts.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): fonts.md | $(OUTPUT_DIR)
	$(TEXSMITH) fonts.md -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

$(TYPST_PDF): fonts.md | $(TYPST_DIR)
	$(TEXSMITH) fonts.md -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
