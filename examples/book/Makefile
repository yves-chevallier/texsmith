OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/book.pdf
BIBER_BIN := $(abspath $(CURDIR)/../../scripts/biber-noop.sh)

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): book.md book.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) -tbook -abibliography_style=numeric
	cd $(OUTPUT_DIR) && lualatex -interaction=nonstopmode -halt-on-error book.tex
	cd $(OUTPUT_DIR) && lualatex -interaction=nonstopmode -halt-on-error book.tex
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
