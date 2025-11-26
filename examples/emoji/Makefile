OUTPUT_DIR := build
SOURCE := emoji.md

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

COLOR_DIR := $(OUTPUT_DIR)/color
BW_DIR := $(OUTPUT_DIR)/bw
DEFAULT_DIR := $(OUTPUT_DIR)/default

COLOR_PDF := $(COLOR_DIR)/emoji-color.pdf
BW_PDF := $(BW_DIR)/emoji-bw.pdf
DEFAULT_PDF := $(DEFAULT_DIR)/emoji-default.pdf

all: $(COLOR_PDF) $(BW_PDF) $(DEFAULT_PDF)

$(COLOR_PDF): $(SOURCE)
	uv run texsmith $< -o$(COLOR_DIR) --build -tarticle -afonts.emoji=color
	mv $(COLOR_DIR)/emoji.pdf $(COLOR_PDF)
	$(call copy_artifact,$@)

$(BW_PDF): $(SOURCE)
	uv run texsmith $< -o$(BW_DIR) --build -tarticle -afonts.emoji=black
	mv $(BW_DIR)/emoji.pdf $(BW_PDF)
	$(call copy_artifact,$@)

$(DEFAULT_PDF): $(SOURCE)
	uv run texsmith $< -o$(DEFAULT_DIR) --build -tarticle
	mv $(DEFAULT_DIR)/emoji.pdf $(DEFAULT_PDF)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
