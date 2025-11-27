include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/cheese$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/cheese.pdf

all: $(PDF)

$(PDF): cheese.md cheese.bib | $(OUTPUT_DIR)
	$(TEXSMITH) $^ -o$(OUTPUT_DIR) -tarticle --build $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
