include ../common.mk

SOURCE := example.md
BASE_PDF := $(ENGINE_DIR)/example.pdf
PDF := $(ENGINE_DIR)/example$(ENGINE_SUFFIX).pdf

all: $(PDF)

$(PDF): $(SOURCE) | $(ENGINE_DIR)
	$(TEXSMITH) $< --build -tarticle -o$(ENGINE_DIR) -M $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
