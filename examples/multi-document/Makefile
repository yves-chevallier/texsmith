include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
FILES := a.md b.md c.md config.yml
PDF := $(OUTPUT_DIR)/multidocument$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/main.pdf

# Typst output -> build/typst/multidocument.pdf: the three documents make one
# main.typ, as they make one main.tex.
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/multidocument.pdf
TYPST_BASE_PDF := $(TYPST_DIR)/main.pdf

ARTIFACTS := $(PDF) $(TYPST_PDF)

all: $(PDF) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(PDF)
typst: $(TYPST_PDF)

$(PDF): $(FILES) | $(OUTPUT_DIR)
	$(TEXSMITH) $^ -o$(OUTPUT_DIR) --build -tarticle $(TEXSMITH_ENGINE)
	mv $(BASE_PDF) $(PDF)
	$(call copy_artifact,$@)

$(TYPST_PDF): $(FILES) | $(TYPST_DIR)
	$(TEXSMITH) $^ -o$(TYPST_DIR) -tarticle --format typst --build
	mv $(TYPST_BASE_PDF) $(TYPST_PDF)
	$(call copy_artifact,$@)

$(TYPST_DIR):
	mkdir -p "$@"

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
.PHONY: all clean latex typst view compare
