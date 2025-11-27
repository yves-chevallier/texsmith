OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/example.pdf
DEPS := $(PDF).d

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): example.md | $(OUTPUT_DIR)
	uv run texsmith $< --build -tarticle -o$(OUTPUT_DIR) -M
	$(call copy_artifact,$@)

$(OUTPUT_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_DIR)

-include $(DEPS)

.PHONY: all clean
