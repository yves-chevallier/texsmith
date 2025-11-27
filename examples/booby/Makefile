include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
SOURCE := booby.md
ASSETS := booby.png
BASE_PDF := $(OUTPUT_DIR)/booby.pdf
PDF := $(OUTPUT_DIR)/booby$(ENGINE_SUFFIX).pdf

all: $(PDF)

$(PDF): $(SOURCE) | $(ASSETS) $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
