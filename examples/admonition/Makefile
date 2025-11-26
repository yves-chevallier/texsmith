OUTPUT_DIR := build
FILES := admonition.md
ASSETS :=

all: $(FILES) | $(ASSETS)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
	cp $(OUTPUT_DIR)/admonition.pdf $(OUTPUT_DIR)/admonition-lualatex.pdf
latex: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle
tectonic: latex
	cd $(OUTPUT_DIR) && tectonic admonition.tex
	cp build/admonition.pdf build/admonition-tectonic.pdf
xelatex: latex
	cd $(OUTPUT_DIR) && latexmk -xelatex admonition.tex
	cp build/admonition.pdf build/admonition-xelatex.pdf
view: tectonic
	evince $(OUTPUT_DIR)/admonition.pdf &
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean latex tectonic xelatex view compare
