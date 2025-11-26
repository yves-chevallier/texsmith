BUILD_ROOT := build
OUTPUT_DIR := $(BUILD_ROOT)/recipes
TEX := $(OUTPUT_DIR)/main.tex
PDF := $(OUTPUT_DIR)/main.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: $(PDF)

$(TEX): cake.yml manifest.toml template.tex render_recipes.py
	uv run python render_recipes.py cake.yml -o $(OUTPUT_DIR)

$(PDF): $(TEX)
	cd $(OUTPUT_DIR) && latexmk -lualatex main.tex
	$(call copy_artifact,$@)

clean:
	rm -rf $(BUILD_ROOT)

.PHONY: all clean
