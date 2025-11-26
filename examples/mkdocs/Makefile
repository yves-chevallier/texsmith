OUTPUT_DIR := press
BOOK_DIR := $(OUTPUT_DIR)/demo
TEX := $(BOOK_DIR)/demo.tex
PDF := $(BOOK_DIR)/demo.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(TEX): mkdocs.yml docs/*.md
	uv run mkdocs build

$(PDF): $(TEX)
	latexmk -cd $(TEX)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR) site

.PHONY: all clean
