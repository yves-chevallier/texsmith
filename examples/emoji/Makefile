OUTPUT_DIR := build
SOURCE := emoji.md

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

PDF := $(OUTPUT_DIR)/emoji.pdf
LUALATEX_PDF := $(OUTPUT_DIR)/emoji-lualatex.pdf

all: $(LUALATEX_PDF)

$(OUTPUT_DIR)/emoji.tex: $(SOURCE)
	uv run texsmith $< -o$(OUTPUT_DIR) -tarticle

$(PDF): $(SOURCE)
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle
	$(call copy_artifact,$@)

$(LUALATEX_PDF): $(PDF)
	cp $(PDF) $(LUALATEX_PDF)
	$(call copy_artifact,$@)

latex: $(OUTPUT_DIR)/emoji.tex

tectonic: $(OUTPUT_DIR)/emoji.tex
	cd $(OUTPUT_DIR) && tectonic emoji.tex
	cp $(OUTPUT_DIR)/emoji.pdf $(OUTPUT_DIR)/emoji-tectonic.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/emoji-tectonic.pdf)

xelatex: $(OUTPUT_DIR)/emoji.tex
	cd $(OUTPUT_DIR) && latexmk -xelatex emoji.tex
	cp $(OUTPUT_DIR)/emoji.pdf $(OUTPUT_DIR)/emoji-xelatex.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/emoji-xelatex.pdf)

view: tectonic
	evince $(OUTPUT_DIR)/emoji.pdf &

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean latex tectonic xelatex view compare
