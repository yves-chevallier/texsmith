include ../common.mk

SOURCE := admonition.md

LATEX_DIR := $(ENGINE_DIR)

CLASSIC_ROOT := build_classic
MINIMAL_ROOT := build_minimal
FANCY_ROOT := build_fancy

CLASSIC_DIR := $(CLASSIC_ROOT)/$(ENGINE)
MINIMAL_DIR := $(MINIMAL_ROOT)/$(ENGINE)
FANCY_DIR := $(FANCY_ROOT)/$(ENGINE)

CLASSIC_PDF := $(CLASSIC_DIR)/admonition-classic$(ENGINE_SUFFIX).pdf
MINIMAL_PDF := $(MINIMAL_DIR)/admonition-minimal$(ENGINE_SUFFIX).pdf
FANCY_PDF := $(FANCY_DIR)/admonition-fancy$(ENGINE_SUFFIX).pdf

CLASSIC_BASE := $(CLASSIC_DIR)/admonition.pdf
MINIMAL_BASE := $(MINIMAL_DIR)/admonition.pdf
FANCY_BASE := $(FANCY_DIR)/admonition.pdf

VARIANTS := $(CLASSIC_PDF) $(MINIMAL_PDF)
ifeq ($(ENGINE),lualatex)
VARIANTS += $(FANCY_PDF)
endif

all: $(VARIANTS)

latex: $(LATEX_DIR)/admonition.tex

$(LATEX_DIR)/admonition.tex: $(SOURCE) | $(LATEX_DIR)
	$(TEXSMITH) $< -o$(LATEX_DIR) -tarticle -acallouts.style=fancy

$(CLASSIC_DIR) $(MINIMAL_DIR) $(FANCY_DIR):
	mkdir -p "$@"

$(CLASSIC_PDF): $(SOURCE) | $(CLASSIC_DIR)
	$(TEXSMITH) $< -o$(CLASSIC_DIR) --build -tarticle -acallouts.style=classic $(TEXSMITH_ENGINE)
	mv $(CLASSIC_BASE) $@
	$(call copy_artifact,$@)

classic: $(CLASSIC_PDF)

$(MINIMAL_PDF): $(SOURCE) | $(MINIMAL_DIR)
	$(TEXSMITH) $< -o$(MINIMAL_DIR) --build -tarticle -acallouts.style=minimal $(TEXSMITH_ENGINE)
	mv $(MINIMAL_BASE) $@
	$(call copy_artifact,$@)

minimal: $(MINIMAL_PDF)

ifeq ($(ENGINE),lualatex)
$(FANCY_PDF): $(SOURCE) | $(FANCY_DIR)
	$(TEXSMITH) $< -o$(FANCY_DIR) --build -tarticle -acallouts.style=fancy -afonts.emoji=color $(TEXSMITH_ENGINE)
	mv $(FANCY_BASE) $@
	$(call copy_artifact,$@)

color: $(FANCY_PDF)
else
$(FANCY_PDF):
	@echo "Color emoji callouts require LuaLaTeX (run 'make lualatex color')."; exit 1

color: $(FANCY_PDF)
endif

clean:
	rm -rf $(OUTPUT_ROOT) $(CLASSIC_ROOT) $(MINIMAL_ROOT) $(FANCY_ROOT)

.PHONY: all clean latex classic minimal color
