include ../common.mk

SOURCE := admonition.md
STYLES := classic minimal fancy

style_pdf = $(OUTPUT_ROOT)/$1/$(ENGINE)/admonition-$1$(ENGINE_SUFFIX).pdf
STYLE_PDFS := $(foreach STYLE,$(STYLES),$(call style_pdf,$(STYLE)))

LATEX_OUTPUT := $(ENGINE_DIR)/admonition.tex

all: $(STYLE_PDFS)

latex: $(LATEX_OUTPUT)

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

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean latex $(STYLES)
