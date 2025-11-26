OUTPUT_DIR := build
PDF := $(OUTPUT_DIR)/cheese.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(PDF): cheese.md cheese.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle
	cd $(OUTPUT_DIR) && lualatex -interaction=nonstopmode -halt-on-error cheese.tex
	cd $(OUTPUT_DIR) && lualatex -interaction=nonstopmode -halt-on-error cheese.tex
	$(call copy_artifact,$@)

latex: cheese.md cheese.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean latex
