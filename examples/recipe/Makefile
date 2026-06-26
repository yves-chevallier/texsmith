include ../common.mk

SOURCE := cake.yml
BASE_PDF := $(ENGINE_DIR)/cake.pdf
PDF := $(ENGINE_DIR)/cake$(ENGINE_SUFFIX).pdf

# Typst output -> build/typst/cake.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/cake.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): $(SOURCE) | $(ENGINE_DIR)
	$(TEXSMITH) $< --build -t. -o$(ENGINE_DIR) -M $(TEXSMITH_ENGINE)
	$(call copy_artifact,$@)

$(TYPST_PDF): $(SOURCE) | $(TYPST_DIR)
	$(TEXSMITH) $< -t. -o$(TYPST_DIR) -M --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
