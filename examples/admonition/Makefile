include ../common.mk

SOURCE := admonition.md
STYLES := classic minimal fancy

# One directory per style and backend: build/<engine>/<style>/admonition-<style>.pdf
# and build/typst/<style>/admonition-<style>.pdf.
style_pdf = $(ENGINE_DIR)/$1/admonition-$1$(ENGINE_SUFFIX).pdf
STYLE_PDFS := $(foreach STYLE,$(STYLES),$(call style_pdf,$(STYLE)))

typst_pdf = $(OUTPUT_ROOT)/typst/$1/admonition-$1.pdf
TYPST_PDFS := $(foreach STYLE,$(STYLES),$(call typst_pdf,$(STYLE)))

ARTIFACTS := $(STYLE_PDFS) $(TYPST_PDFS)

all: $(STYLE_PDFS) $(TYPST_PDFS)

# Build a single backend on demand.
latex: $(STYLE_PDFS)
typst: $(TYPST_PDFS)

define RENDER_STYLE
$(call style_pdf,$1): $(SOURCE)
	@mkdir -p $$(dir $$@)
	$(TEXSMITH) $$< -o$$(dir $$@) --build -tarticle -acallouts.style=$1 \
		$$(if $$(filter fancy,$1),-afonts.emoji=color,) $(TEXSMITH_ENGINE)
	mv $$(dir $$@)admonition.pdf $$@
	$(call copy_artifact,$$@)

$1: $(call style_pdf,$1)
endef

$(foreach STYLE,$(STYLES),$(eval $(call RENDER_STYLE,$(STYLE))))

define RENDER_TYPST_STYLE
$(call typst_pdf,$1): $(SOURCE)
	@mkdir -p $$(dir $$@)
	$(TEXSMITH) $$< -o$$(dir $$@) -tarticle --format typst --build -acallouts.style=$1
	mv $$(dir $$@)admonition.pdf $$@
	$(call copy_artifact,$$@)
endef

$(foreach STYLE,$(STYLES),$(eval $(call RENDER_TYPST_STYLE,$(STYLE))))

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean latex typst $(STYLES)
