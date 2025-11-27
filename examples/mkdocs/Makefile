OUTPUT_ROOT := press
include ../common.mk

BOOK_DIR := $(OUTPUT_ROOT)/demo
TEX := $(BOOK_DIR)/demo.tex
PDF := $(BOOK_DIR)/demo$(ENGINE_SUFFIX).pdf
BASE_PDF := $(BOOK_DIR)/demo.pdf
UV_WITH ?= --with mkdocs --with mkdocs-material --with mkdocs-autorefs --with ../../packages/mkdocs_texsmith

ifeq ($(ENGINE),xelatex)
LATEXMK_ENGINE_FLAG := -xelatex
else ifeq ($(ENGINE),lualatex)
LATEXMK_ENGINE_FLAG := -lualatex
endif

all: $(PDF)

$(TEX): mkdocs.yml docs/*.md
	uv run $(UV_WITH) mkdocs build

$(PDF): $(TEX)
ifneq ($(ENGINE),tectonic)
	latexmk -cd $(LATEXMK_ENGINE_FLAG) $(TEX)
else
	cd $(BOOK_DIR) && tectonic $(notdir $(TEX))
endif
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT) site

.PHONY: all clean
