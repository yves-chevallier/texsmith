OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/example.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): example.md
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle -apress.override.preamble="\\usepackage{progressbar}"
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
