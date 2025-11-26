OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/letter.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): letter.md marie-curie.svg
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tletter
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
