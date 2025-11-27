include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/snippet$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/snippet.pdf

all: $(PDF)

$(PDF): docs/index.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	mv $(OUTPUT_DIR)/index.pdf $(PDF)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
