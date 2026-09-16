include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
SOURCE := box-drawing.md
BASE_PDF := $(OUTPUT_DIR)/box-drawing.pdf
PDF := $(OUTPUT_DIR)/box-drawing$(ENGINE_SUFFIX).pdf

# LaTeX only: what the document exercises is the fontspec fallback the
# `scripts` pass builds, which Typst has no equivalent of — it picks a font
# per character itself.
ARTIFACTS := $(PDF)

all: $(PDF)

latex: $(PDF)

$(PDF): $(SOURCE) | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all latex clean
