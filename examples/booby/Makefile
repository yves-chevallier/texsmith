OUTPUT_DIR := build
SOURCE := booby.md
ASSETS := booby.png

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

PDF := $(OUTPUT_DIR)/booby.pdf
LUALATEX_PDF := $(OUTPUT_DIR)/booby-lualatex.pdf

all: $(LUALATEX_PDF)

$(OUTPUT_DIR)/booby.tex: $(SOURCE) | $(ASSETS)
	uv run texsmith $< -o$(OUTPUT_DIR) -tarticle

$(PDF): $(SOURCE) | $(ASSETS)
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle
	$(call copy_artifact,$@)

$(LUALATEX_PDF): $(PDF)
	cp $(PDF) $(LUALATEX_PDF)
	$(call copy_artifact,$(LUALATEX_PDF))

latex: $(OUTPUT_DIR)/booby.tex

tectonic: $(OUTPUT_DIR)/booby.tex
	cd $(OUTPUT_DIR) && tectonic booby.tex
	cp $(OUTPUT_DIR)/booby.pdf $(OUTPUT_DIR)/booby-tectonic.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/booby-tectonic.pdf)

xelatex: $(OUTPUT_DIR)/booby.tex
	cd $(OUTPUT_DIR) && latexmk -xelatex booby.tex
	cp $(OUTPUT_DIR)/booby.pdf $(OUTPUT_DIR)/booby-xelatex.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/booby-xelatex.pdf)

view: tectonic
	evince $(OUTPUT_DIR)/booby.pdf &

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean latex tectonic xelatex view compare
