OUTPUT_DIR := build
FILES := booby.md
ASSETS := booby.png

all: $(FILES) | $(ASSETS)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
	cp $(OUTPUT_DIR)/booby.pdf $(OUTPUT_DIR)/booby-lualatex.pdf
latex: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle
tectonic: latex
	cd $(OUTPUT_DIR) && tectonic booby.tex
	cp build/booby.pdf build/booby-tectonic.pdf
xelatex: latex
	cd $(OUTPUT_DIR) && latexmk -xelatex booby.tex
	cp build/booby.pdf build/booby-xelatex.pdf
view: tectonic
	evince $(OUTPUT_DIR)/booby.pdf &
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean latex tectonic xelatex view compare
