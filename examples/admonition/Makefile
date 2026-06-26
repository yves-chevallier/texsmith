include ../common.mk

SOURCE := admonition.md
STYLES := classic minimal fancy

style_pdf = $(OUTPUT_ROOT)/$1/$(ENGINE)/admonition-$1$(ENGINE_SUFFIX).pdf
STYLE_PDFS := $(foreach STYLE,$(STYLES),$(call style_pdf,$(STYLE)))

LATEX_OUTPUT := $(ENGINE_DIR)/admonition.tex

# Typst output -> build/typst/admonition.pdf. The callouts.style variants are
# LaTeX-only (callout themes); the Typst backend renders a single block style.
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_PDF := $(TYPST_DIR)/admonition.pdf

ARTIFACTS := $(STYLE_PDFS) $(TYPST_PDF)

all: $(STYLE_PDFS) $(TYPST_PDF)

# Build a single backend on demand.
latex: $(STYLE_PDFS)
typst: $(TYPST_PDF)

# Emit the LaTeX .tex source (fancy style) without building.
tex: $(LATEX_OUTPUT)

$(LATEX_OUTPUT): $(SOURCE) | $(ENGINE_DIR)
	$(TEXSMITH) $< -o$(ENGINE_DIR) -tarticle -acallouts.style=fancy

$(TYPST_DIR):
	mkdir -p "$@"

$(TYPST_PDF): $(SOURCE) | $(TYPST_DIR)
	$(TEXSMITH) $< -o$(TYPST_DIR) -tarticle --format typst --build
	$(call copy_artifact,$@)

define RENDER_STYLE
$(call style_pdf,$1): $(SOURCE)
	@mkdir -p $$(dir $$@)
	$(TEXSMITH) $$< -o$$(dir $$@) --build -tarticle -acallouts.style=$1 \
		$$(if $$(filter fancy,$1),-afonts.emoji=color,) $(TEXSMITH_ENGINE)
	cp $$(dir $$@)admonition.pdf $$@
	$(call copy_artifact,$$@)

$1: $(call style_pdf,$1)
endef

$(foreach STYLE,$(STYLES),$(eval $(call RENDER_STYLE,$(STYLE))))

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean latex tex typst $(STYLES)
