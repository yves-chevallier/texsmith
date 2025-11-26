
OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/diagrams.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): diagrams.md pgcd.drawio
	uv run texsmith diagrams.md -tarticle -o$(OUTPUT_DIR) --build --title-from-frontmatter
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
