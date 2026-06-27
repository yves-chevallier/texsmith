include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/math$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/math.pdf

# Typst output -> build/typst/math.pdf (engine-agnostic, native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/math.pdf

# `make` builds BOTH the LaTeX and the Typst PDF.
ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): math.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle -apress.override.preamble="\\usepackage{csquotes}" $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

# The csquotes preamble override is LaTeX-only; the Typst backend renders math
# through mitex and needs no extra packages.
$(TYPST_PDF): math.md | $(TYPST_DIR)
	$(TEXSMITH) $< -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex typst clean
