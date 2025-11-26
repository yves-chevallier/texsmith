OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/features.pdf
ASSETS := assets/sample.png hanoi.py

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): features.md $(ASSETS)
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
