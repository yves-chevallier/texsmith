include ../common.mk

SOURCE := admonition.md
STYLES := classic minimal fancy

style_pdf = $(OUTPUT_ROOT)/$1/$(ENGINE)/admonition-$1$(ENGINE_SUFFIX).pdf
STYLE_PDFS := $(foreach STYLE,$(STYLES),$(call style_pdf,$(STYLE)))

LATEX_OUTPUT := $(ENGINE_DIR)/admonition.tex

# Typst output -> build/typst/<style>/admonition-<style>.pdf. The Typst backend
# now honours callouts.style too (fancy/classic/minimal), so the three style
# variants are built for Typst exactly as for LaTeX.
typst_pdf = $(OUTPUT_ROOT)/typst/$1/admonition-$1.pdf
TYPST_PDFS := $(foreach STYLE,$(STYLES),$(call typst_pdf,$(STYLE)))

ARTIFACTS := $(STYLE_PDFS) $(TYPST_PDFS)

all: $(STYLE_PDFS) $(TYPST_PDFS)

# Build a single backend on demand.
latex: $(STYLE_PDFS)
typst: $(TYPST_PDFS)

# Emit the LaTeX .tex source (fancy style) without building.
tex: $(LATEX_OUTPUT)

$(LATEX_OUTPUT): $(SOURCE) | $(ENGINE_DIR)
	$(TEXSMITH) $< -o$(ENGINE_DIR) -tarticle -acallouts.style=fancy

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

define RENDER_TYPST_STYLE
$(call typst_pdf,$1): $(SOURCE)
	@mkdir -p $$(dir $$@)
	$(TEXSMITH) $$< -o$$(dir $$@) -tarticle --format typst --build -acallouts.style=$1
	cp $$(dir $$@)admonition.pdf $$@
	$(call copy_artifact,$$@)
endef

$(foreach STYLE,$(STYLES),$(eval $(call RENDER_TYPST_STYLE,$(STYLE))))

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean latex tex typst $(STYLES)
