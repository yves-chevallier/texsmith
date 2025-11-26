export ARTIFACTS_DIR ?= $(CURDIR)/examples_build

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
	paper \
	progressbar \
	recipe \
	snippet

EXAMPLES_WITH_TECTONIC := admonition booby emoji multi-document
EXAMPLES_WITH_COMPARE := multi-document

all:
	@for example in $(EXAMPLES); do \
		$(MAKE) -C $$example all; \
	done

tectonic:
	@for example in $(EXAMPLES_WITH_TECTONIC); do \
		$(MAKE) -C $$example tectonic; \
	done

compare:
	@for example in $(EXAMPLES_WITH_COMPARE); do \
		$(MAKE) -C $$example compare; \
	done

clean:
	$(RM) -rf $(ARTIFACTS_DIR)
	@for example in $(EXAMPLES); do \
		$(MAKE) -C $$example clean; \
	done

.PHONY: all clean tectonic compare
