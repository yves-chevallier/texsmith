export ARTIFACTS_DIR ?= $(CURDIR)/examples_build
ENGINE ?= tectonic

EXAMPLES := \
	abbr \
	admonition \
	booby \
	book \
	code \
	colorful \
	diagrams \
	dialects \
	emoji \
	fonts \
	index \
	letter \
	markdown \
	math \
	mermaid \
	multi-document \
	mkdocs \
	paper \
	progressbar \
	recipe \
	snippet

EXAMPLES_WITH_COMPARE := multi-document

all:
	@for example in $(EXAMPLES); do \
		$(MAKE) -C $$example ENGINE=$(ENGINE) all; \
	done

compare:
	@for example in $(EXAMPLES_WITH_COMPARE); do \
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
	@for example in $(EXAMPLES); do \
		$(MAKE) -C $$example clean; \
	done

.PHONY: all clean tectonic compare lualatex xelatex
