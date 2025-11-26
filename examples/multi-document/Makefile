OUTPUT_DIR := build
FILES := a.md b.md c.md config.yml
PDF := $(OUTPUT_DIR)/multidocument.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
	mv $(OUTPUT_DIR)/main.pdf $(PDF)
	$(call copy_artifact,$@)

latex: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle

tectonic: latex
	cd $(OUTPUT_DIR) && tectonic main.tex
	cp $(OUTPUT_DIR)/main.pdf $(OUTPUT_DIR)/multidocument-tectonic.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/multidocument-tectonic.pdf)

xelatex: latex
	cd $(OUTPUT_DIR) && latexmk -xelatex main.tex
	cp $(OUTPUT_DIR)/main.pdf $(OUTPUT_DIR)/multidocument-xelatex.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/multidocument-xelatex.pdf)

view: $(PDF)
	evince $(PDF) &
COMPARE_TMP := overlay_tmp
COMPARE_OUT := overlay.pdf

compare: 1.pdf 2.pdf 3.pdf
	@rm -rf $(COMPARE_TMP)
	mkdir -p $(COMPARE_TMP)
	pdftocairo -singlefile -transp -png -r 300 1.pdf $(COMPARE_TMP)/1
	pdftocairo -singlefile -transp -png -r 300 2.pdf $(COMPARE_TMP)/2
	pdftocairo -singlefile -transp -png -r 300 3.pdf $(COMPARE_TMP)/3
	convert $(COMPARE_TMP)/1.png -fill red   -colorize 100 -alpha set -channel A -evaluate multiply 0.5 $(COMPARE_TMP)/1_tinted.png
	convert $(COMPARE_TMP)/2.png -fill green -colorize 100 -alpha set -channel A -evaluate multiply 0.5 $(COMPARE_TMP)/2_tinted.png
	convert $(COMPARE_TMP)/3.png -fill blue  -colorize 100 -alpha set -channel A -evaluate multiply 0.5 $(COMPARE_TMP)/3_tinted.png
	convert $(COMPARE_TMP)/1_tinted.png $(COMPARE_TMP)/2_tinted.png $(COMPARE_TMP)/3_tinted.png -background none -layers merge $(COMPARE_OUT)
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean latex tectonic xelatex view compare
