include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
SOURCE := booby.md
ASSETS := booby.png
BASE_PDF := $(OUTPUT_DIR)/booby.pdf
PDF := $(OUTPUT_DIR)/booby$(ENGINE_SUFFIX).pdf

# Typst output -> build/typst/booby.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/booby.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): $(SOURCE) | $(ASSETS) $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

$(TYPST_PDF): $(SOURCE) | $(ASSETS) $(TYPST_DIR)
	$(TEXSMITH) $< -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
