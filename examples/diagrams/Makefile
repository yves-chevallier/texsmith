include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/diagrams$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/diagrams.pdf

all: $(PDF)

$(PDF): diagrams.md pgcd.drawio | $(OUTPUT_DIR)
	$(TEXSMITH) diagrams.md -tarticle -o$(OUTPUT_DIR) --build $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	-rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
