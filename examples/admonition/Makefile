OUTPUT_DIR := build
FILES := admonition.md

all: color classic minimal

black: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle -afonts.emoji=black -acallouts.style=fancy
	mv $(OUTPUT_DIR)/admonition.pdf $(OUTPUT_DIR)/admonition-black.pdf
color: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=fancy
	mv $(OUTPUT_DIR)/admonition.pdf $(OUTPUT_DIR)/admonition-fancy.pdf
classic: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=classic
	mv $(OUTPUT_DIR)/admonition.pdf $(OUTPUT_DIR)/admonition-classic.pdf
minimal: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=minimal
	mv $(OUTPUT_DIR)/admonition.pdf $(OUTPUT_DIR)/admonition-minimal.pdf


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
