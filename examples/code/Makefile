include ../common.mk

OUTPUT_DIR_BLOCK := $(ENGINE_DIR)/block
OUTPUT_DIR_INLINE := $(ENGINE_DIR)/inline
BLOCK_PDF := $(OUTPUT_DIR_BLOCK)/code-block$(ENGINE_SUFFIX).pdf
BLOCK_BASE := $(OUTPUT_DIR_BLOCK)/code-block.pdf
INLINE_PDF := $(OUTPUT_DIR_INLINE)/code-inline$(ENGINE_SUFFIX).pdf
INLINE_BASE := $(OUTPUT_DIR_INLINE)/code-inline.pdf
ARTIFACTS := $(BLOCK_PDF) $(INLINE_PDF)

$(OUTPUT_DIR_BLOCK) $(OUTPUT_DIR_INLINE):
	mkdir -p "$@"

all: block inline

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

clean:
	rm -rf $(OUTPUT_ROOT)

.PHONY: all clean block inline
