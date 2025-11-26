OUTPUT_DIR := build
SOURCE := admonition.md

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

COLOR_PDF := $(OUTPUT_DIR)/admonition-fancy.pdf
CLASSIC_PDF := $(OUTPUT_DIR)/admonition-classic.pdf
MINIMAL_PDF := $(OUTPUT_DIR)/admonition-minimal.pdf
BLACK_PDF := $(OUTPUT_DIR)/admonition-black.pdf

all: color classic minimal black

latex: $(OUTPUT_DIR)/admonition.tex

$(OUTPUT_DIR)/admonition.tex: $(SOURCE)
	uv run texsmith $< -o$(OUTPUT_DIR) -tarticle -acallouts.style=fancy

black: $(SOURCE)
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle -afonts.emoji=black -acallouts.style=fancy
	mv $(OUTPUT_DIR)/admonition.pdf $(BLACK_PDF)
	$(call copy_artifact,$(BLACK_PDF))

color: $(SOURCE)
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=fancy
	mv $(OUTPUT_DIR)/admonition.pdf $(COLOR_PDF)
	$(call copy_artifact,$(COLOR_PDF))

classic: $(SOURCE)
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=classic
	mv $(OUTPUT_DIR)/admonition.pdf $(CLASSIC_PDF)
	$(call copy_artifact,$(CLASSIC_PDF))

minimal: $(SOURCE)
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=minimal
	mv $(OUTPUT_DIR)/admonition.pdf $(MINIMAL_PDF)
	$(call copy_artifact,$(MINIMAL_PDF))

tectonic: latex
	cd $(OUTPUT_DIR) && tectonic admonition.tex
	cp $(OUTPUT_DIR)/admonition.pdf $(OUTPUT_DIR)/admonition-tectonic.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/admonition-tectonic.pdf)

xelatex: latex
	cd $(OUTPUT_DIR) && latexmk -xelatex admonition.tex
	cp $(OUTPUT_DIR)/admonition.pdf $(OUTPUT_DIR)/admonition-xelatex.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/admonition-xelatex.pdf)

view: tectonic
	evince $(OUTPUT_DIR)/admonition.pdf &

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean latex tectonic xelatex view compare black color classic minimal
