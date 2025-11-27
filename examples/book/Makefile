include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/book$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/book.pdf

all: $(PDF)

$(PDF): book.md book.bib
	$(TEXSMITH) $^ -o$(OUTPUT_DIR) --build -tbook -abibliography_style=numeric $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
