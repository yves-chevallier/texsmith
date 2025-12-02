include ../common.mk

SOURCE := cake.yml
BASE_PDF := $(ENGINE_DIR)/cake.pdf
PDF := $(ENGINE_DIR)/cake$(ENGINE_SUFFIX).pdf

all: $(PDF)

$(PDF): $(SOURCE) | $(ENGINE_DIR)
	$(TEXSMITH) $< --build -t. -o$(ENGINE_DIR) -M $(TEXSMITH_ENGINE)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
