include ../common.mk

OUTPUT_DIR := $(ENGINE_DIR)
SOURCE := admonition.md

COLOR_PDF := $(OUTPUT_DIR)/admonition-fancy$(ENGINE_SUFFIX).pdf
CLASSIC_PDF := $(OUTPUT_DIR)/admonition-classic$(ENGINE_SUFFIX).pdf
MINIMAL_PDF := $(OUTPUT_DIR)/admonition-minimal$(ENGINE_SUFFIX).pdf
BLACK_PDF := $(OUTPUT_DIR)/admonition-black$(ENGINE_SUFFIX).pdf
BASE_PDF := $(OUTPUT_DIR)/admonition.pdf

all: color classic minimal black

latex: $(OUTPUT_DIR)/admonition.tex

$(OUTPUT_DIR)/admonition.tex: $(SOURCE) | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) -tarticle -acallouts.style=fancy

black: $(SOURCE) | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle -afonts.emoji=black -acallouts.style=fancy $(TEXSMITH_ENGINE)
	mv $(BASE_PDF) $(BLACK_PDF)
	$(call copy_artifact,$(BLACK_PDF))

color: $(SOURCE) | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=fancy $(TEXSMITH_ENGINE)
	mv $(BASE_PDF) $(COLOR_PDF)
	$(call copy_artifact,$(COLOR_PDF))

classic: $(SOURCE) | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=classic $(TEXSMITH_ENGINE)
	mv $(BASE_PDF) $(CLASSIC_PDF)
	$(call copy_artifact,$(CLASSIC_PDF))

minimal: $(SOURCE) | $(OUTPUT_DIR)
	$(TEXSMITH) $< -o$(OUTPUT_DIR) --build -tarticle -acallouts.style=minimal $(TEXSMITH_ENGINE)
	mv $(BASE_PDF) $(MINIMAL_PDF)
	$(call copy_artifact,$(MINIMAL_PDF))

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean latex black color classic minimal
