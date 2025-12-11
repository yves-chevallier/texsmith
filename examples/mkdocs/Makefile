OUTPUT_ROOT := press
include ../common.mk

PDF := $(OUTPUT_ROOT)/demo/demo.pdf
MKDOCS_PDF := press/mkdocs.pdf
ARTIFACTS := $(MKDOCS_PDF)

all: $(MKDOCS_PDF)

$(PDF):
	TEXSMITH_BUILD=1 uv run mkdocs build

$(MKDOCS_PDF): $(PDF)
	cp $< $@

clean:
	rm -rf press site

.PHONY: all clean
