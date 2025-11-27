include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
SOURCE := emoji.md

COLOR_DIR := $(OUTPUT_DIR)/color
BW_DIR := $(OUTPUT_DIR)/bw
DEFAULT_DIR := $(OUTPUT_DIR)/default

COLOR_PDF := $(COLOR_DIR)/emoji-color$(ENGINE_SUFFIX).pdf
BW_PDF := $(BW_DIR)/emoji-bw$(ENGINE_SUFFIX).pdf
DEFAULT_PDF := $(DEFAULT_DIR)/emoji-default$(ENGINE_SUFFIX).pdf
COLOR_BASE := $(COLOR_DIR)/emoji.pdf
BW_BASE := $(BW_DIR)/emoji.pdf
DEFAULT_BASE := $(DEFAULT_DIR)/emoji.pdf

$(COLOR_DIR) $(BW_DIR) $(DEFAULT_DIR): | $(OUTPUT_DIR)
	mkdir -p "$@"

all: $(COLOR_PDF) $(BW_PDF) $(DEFAULT_PDF)

$(COLOR_PDF): $(SOURCE) | $(COLOR_DIR)
	$(TEXSMITH) $< -o$(COLOR_DIR) --build -tarticle -afonts.emoji=color $(TEXSMITH_ENGINE)
	mv $(COLOR_BASE) $(COLOR_PDF)
	$(call copy_artifact,$@)

$(BW_PDF): $(SOURCE) | $(BW_DIR)
	$(TEXSMITH) $< -o$(BW_DIR) --build -tarticle -afonts.emoji=black $(TEXSMITH_ENGINE)
	mv $(BW_BASE) $(BW_PDF)
	$(call copy_artifact,$@)

$(DEFAULT_PDF): $(SOURCE) | $(DEFAULT_DIR)
	$(TEXSMITH) $< -o$(DEFAULT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	mv $(DEFAULT_BASE) $(DEFAULT_PDF)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
