OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/dialects.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): dialects.md
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle
	$(call copy_artifact,$@)

latex: dialects.md
	uv run texsmith $< -o$(OUTPUT_DIR) -tarticle

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean latex
