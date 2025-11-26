OUTPUT_DIR := build
FILES := a.md b.md c.md config.yml
PDF := $(OUTPUT_DIR)/main.pdf
LUALATEX_PDF := $(OUTPUT_DIR)/main-lualatex.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(LUALATEX_PDF)

$(OUTPUT_DIR)/main.tex: $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle

$(PDF): $(FILES)
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
	$(call copy_artifact,$@)

$(LUALATEX_PDF): $(PDF)
	cp $(PDF) $(LUALATEX_PDF)
	$(call copy_artifact,$@)

latex: $(OUTPUT_DIR)/main.tex

tectonic: $(OUTPUT_DIR)/main.tex
	cd $(OUTPUT_DIR) && tectonic main.tex
	cp $(OUTPUT_DIR)/main.pdf $(OUTPUT_DIR)/main-tectonic.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/main-tectonic.pdf)

xelatex: $(OUTPUT_DIR)/main.tex
	cd $(OUTPUT_DIR) && latexmk -xelatex main.tex
	cp $(OUTPUT_DIR)/main.pdf $(OUTPUT_DIR)/main-xelatex.pdf
	$(call copy_artifact,$(OUTPUT_DIR)/main-xelatex.pdf)

view: tectonic
	evince $(OUTPUT_DIR)/main.pdf &
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
