include ../common.mk

SOURCE := letter.md marie-curie.svg
# The three national standards the letter template lays out, on both backends:
# build/<engine>/<format>/letter-<format>.pdf and build/typst/<format>/letter-<format>.pdf.
FORMATS := din sn nf

latex_pdf = $(ENGINE_DIR)/$1/letter-$1$(ENGINE_SUFFIX).pdf
LATEX_PDFS := $(foreach FORMAT,$(FORMATS),$(call latex_pdf,$(FORMAT)))

typst_pdf = $(OUTPUT_ROOT)/typst/$1/letter-$1.pdf
TYPST_PDFS := $(foreach FORMAT,$(FORMATS),$(call typst_pdf,$(FORMAT)))

ARTIFACTS := $(LATEX_PDFS) $(TYPST_PDFS)

all: $(LATEX_PDFS) $(TYPST_PDFS)

# Build a single backend on demand.
latex: $(LATEX_PDFS)
typst: $(TYPST_PDFS)

define RENDER_LATEX
$(call latex_pdf,$1): $(SOURCE)
	@mkdir -p $$(dir $$@)
	$(TEXSMITH) $$< -o$$(dir $$@) --build -tletter -aformat=$1 $(TEXSMITH_ENGINE)
	mv $$(dir $$@)letter.pdf $$@
	$(call copy_artifact,$$@)

$1: $(call latex_pdf,$1)
endef

$(foreach FORMAT,$(FORMATS),$(eval $(call RENDER_LATEX,$(FORMAT))))

define RENDER_TYPST
$(call typst_pdf,$1): $(SOURCE)
	@mkdir -p $$(dir $$@)
	$(TEXSMITH) $$< -o$$(dir $$@) -tletter --format typst --build -aformat=$1
	mv $$(dir $$@)letter.pdf $$@
	$(call copy_artifact,$$@)
endef

$(foreach FORMAT,$(FORMATS),$(eval $(call RENDER_TYPST,$(FORMAT))))

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean latex typst $(FORMATS)
