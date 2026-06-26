include ../common.mk

OUTPUT_DIR_BLOCK := $(ENGINE_DIR)/block
OUTPUT_DIR_INLINE := $(ENGINE_DIR)/inline
BLOCK_PDF := $(OUTPUT_DIR_BLOCK)/code-block$(ENGINE_SUFFIX).pdf
BLOCK_BASE := $(OUTPUT_DIR_BLOCK)/code-block.pdf
INLINE_PDF := $(OUTPUT_DIR_INLINE)/code-inline$(ENGINE_SUFFIX).pdf
INLINE_BASE := $(OUTPUT_DIR_INLINE)/code-inline.pdf

# Typst output -> build/typst/code-{block,inline}.pdf (native Typst compiler)
TYPST_DIR := $(OUTPUT_ROOT)/typst
TYPST_BLOCK_PDF := $(TYPST_DIR)/code-block.pdf
TYPST_INLINE_PDF := $(TYPST_DIR)/code-inline.pdf

# `make` builds BOTH the LaTeX and the Typst PDFs.
ARTIFACTS := $(BLOCK_PDF) $(INLINE_PDF) $(TYPST_BLOCK_PDF) $(TYPST_INLINE_PDF)

$(OUTPUT_DIR_BLOCK) $(OUTPUT_DIR_INLINE) $(TYPST_DIR):
	mkdir -p "$@"

all: block inline typst

# Build a single backend on demand.
latex: block inline
typst: $(TYPST_BLOCK_PDF) $(TYPST_INLINE_PDF)

block: $(BLOCK_PDF)

$(BLOCK_PDF): code-block.md | $(OUTPUT_DIR_BLOCK)
	$(TEXSMITH) $< -o$(OUTPUT_DIR_BLOCK) --build $(TEXSMITH_ENGINE)
	if [ "$(BLOCK_PDF)" != "$(BLOCK_BASE)" ]; then mv "$(BLOCK_BASE)" "$(BLOCK_PDF)"; fi
	$(call copy_artifact,$(BLOCK_PDF))

inline: $(INLINE_PDF)

$(INLINE_PDF): code-inline.md | $(OUTPUT_DIR_INLINE)
	$(TEXSMITH) $< -o$(OUTPUT_DIR_INLINE) --build $(TEXSMITH_ENGINE)
	if [ "$(INLINE_PDF)" != "$(INLINE_BASE)" ]; then mv "$(INLINE_BASE)" "$(INLINE_PDF)"; fi
	$(call copy_artifact,$(INLINE_PDF))

$(TYPST_BLOCK_PDF): code-block.md | $(TYPST_DIR)
	$(TEXSMITH) $< -o$(TYPST_DIR) --format typst --build
	$(call copy_artifact,$@)

$(TYPST_INLINE_PDF): code-inline.md | $(TYPST_DIR)
	$(TEXSMITH) $< -o$(TYPST_DIR) --format typst --build
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean latex typst block inline
