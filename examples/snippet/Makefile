OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/snippet.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): docs/index.md
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle
	mv $(OUTPUT_DIR)/index.pdf $(PDF)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
