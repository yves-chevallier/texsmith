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

all: $(EXAMPLES:%=%/all)

tectonic: $(EXAMPLES_WITH_TECTONIC:%=%/tectonic)

compare: $(EXAMPLES_WITH_COMPARE:%=%/compare)

clean:
	$(RM) -rf $(ARTIFACTS_DIR)
	@for example in $(EXAMPLES); do \
		$(MAKE) -C $$example clean; \
	done

.PHONY: all clean tectonic compare
