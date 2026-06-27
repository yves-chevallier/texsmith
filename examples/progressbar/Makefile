include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/progressbar$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/progressbar.pdf

# Typst output -> build/typst/progressbar.pdf (engine-agnostic, native compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/progressbar.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): progressbar.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle -apress.override.preamble="\\usepackage{progressbar}" $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

# The progressbar LaTeX package is LaTeX-only; the Typst backend draws the bar
# from native #box primitives, so no preamble override is needed.
$(TYPST_PDF): progressbar.md | $(TYPST_DIR)
	$(TEXSMITH) $< -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
