OUTPUT_DIR := build
FILES := emoji.md
ASSETS :=

all: $(FILES) | $(ASSETS)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
	cp $(OUTPUT_DIR)/emoji.pdf $(OUTPUT_DIR)/emoji-lualatex.pdf
latex: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle
tectonic: latex
	cd $(OUTPUT_DIR) && tectonic emoji.tex
	cp build/emoji.pdf build/emoji-tectonic.pdf
xelatex: latex
	cd $(OUTPUT_DIR) && latexmk -xelatex emoji.tex
	cp build/emoji.pdf build/emoji-xelatex.pdf
view: tectonic
	evince $(OUTPUT_DIR)/emoji.pdf &
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean latex tectonic xelatex view compare
