OUTPUT_ROOT := build
include ../common.mk

ENGINE_FOR_BUILD := $(ENGINE)
ENGINE_SUFFIX := $(if $(filter $(ENGINE_FOR_BUILD),tectonic),,$(addprefix -,$(ENGINE_FOR_BUILD)))
OUTPUT_DIR := $(OUTPUT_ROOT)/$(ENGINE_FOR_BUILD)/recipes
TEX := $(OUTPUT_DIR)/cake.tex
PDF := $(OUTPUT_DIR)/cake$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/cake.pdf

ifeq ($(ENGINE_FOR_BUILD),xelatex)
LATEXMK_ENGINE_FLAG := -xelatex
else ifeq ($(ENGINE_FOR_BUILD),lualatex)
LATEXMK_ENGINE_FLAG := -lualatex
endif

$(OUTPUT_DIR):
	mkdir -p "$@"

all: $(PDF)

$(TEX): cake.yml manifest.toml template.tex render_recipes.py
	uv run python render_recipes.py cake.yml -o $(OUTPUT_DIR)

$(PDF): $(TEX)
ifneq ($(ENGINE_FOR_BUILD),tectonic)
	latexmk -cd $(LATEXMK_ENGINE_FLAG) $(TEX)
else
	cd $(OUTPUT_DIR) && tectonic $(notdir $(TEX))
endif
	if [ "$(PDF)" != "$(BASE_PDF)" ]; then mv "$(BASE_PDF)" "$(PDF)"; fi
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean
