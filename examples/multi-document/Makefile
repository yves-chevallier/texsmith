include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
FILES := a.md b.md c.md config.yml
PDF := $(OUTPUT_DIR)/multidocument$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/main.pdf

all: $(PDF)

$(PDF): $(FILES) | $(OUTPUT_DIR)
	$(TEXSMITH) $^ -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	mv $(BASE_PDF) $(PDF)
	$(call copy_artifact,$@)

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
	rm -rf $(OUTPUT_ROOT)
.PHONY: all clean view compare
