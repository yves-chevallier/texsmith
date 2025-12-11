OUTPUT_ROOT := press
include ../common.mk

PDF := $(OUTPUT_ROOT)/demo/demo.pdf

all: $(PDF)

$(PDF):
	TEXSMITH_BUILD=1 uv run mkdocs build
	cp $@ press/mkdocs.pdf
	$(call copy_artifact,press/mkdocs.pdf)

clean:
	rm -rf press site

.PHONY: all clean
