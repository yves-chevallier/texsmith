OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/book.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(OUTPUT_DIR)/book.tex: book.md book.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle -abibliography_style=numeric

$(PDF): $(OUTPUT_DIR)/book.tex
	cd $(OUTPUT_DIR) && biber book
	cd $(OUTPUT_DIR) && latexmk -lualatex book.tex
	$(call copy_artifact,$@)

latex: $(OUTPUT_DIR)/book.tex

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean latex
