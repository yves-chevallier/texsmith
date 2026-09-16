export ARTIFACTS_DIR ?= $(CURDIR)/build
ENGINE ?= tectonic

EXAMPLES := \
	abbr \
	admonition \
	booby \
	box-drawing \
	book \
	book-fr \
	code \
	colorful \
	counters \
	diagrams \
	dialects \
	emoji \
	fonts \
	glossary \
	index \
	letter \
	marginnote \
	tmark \
	math \
	mermaid \
	multi-document \
	nested-lists \
	mkdocs \
	paper \
	progressbar \
	recipe \
	snippet \
	tables

EXAMPLES_WITH_COMPARE := multi-document

# Examples that expose a `typst` target (the mkdocs example has no Typst path).
TYPST_EXAMPLES := $(filter-out mkdocs,$(EXAMPLES))

all:
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C $$example ENGINE=$(ENGINE) all; \
	done

# Build only the Typst PDFs across every example (engine-agnostic).
typst:
	@set -e; \
	for example in $(TYPST_EXAMPLES); do \
		$(MAKE) -C $$example typst; \
	done

compare:
	@set -e; \
	for example in $(EXAMPLES_WITH_COMPARE); do \
		$(MAKE) -C $$example compare; \
	done

tectonic:
	$(MAKE) ENGINE=tectonic all

lualatex:
	$(MAKE) ENGINE=lualatex all

xelatex:
	$(MAKE) ENGINE=xelatex all

clean:
	$(RM) -rf $(ARTIFACTS_DIR)
	@set -e; \
	for example in $(EXAMPLES); do \
		$(MAKE) -C $$example clean; \
	done

.PHONY: all clean tectonic compare lualatex xelatex typst
