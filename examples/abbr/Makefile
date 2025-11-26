OUTPUT_DIR := build

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: example.md
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
	$(call copy_artifact,$(OUTPUT_DIR)/example.pdf)
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean
