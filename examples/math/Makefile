include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
PDF := $(OUTPUT_DIR)/math$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/math.pdf

all: $(PDF)

$(PDF): math.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle -apress.override.preamble="\\usepackage{csquotes}" $(TEXSMITH_ENGINE)
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
