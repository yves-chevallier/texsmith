OUTPUT_DIR_BLOCK := build_block
OUTPUT_DIR_INLINE := build_inline
BLOCK_PDF := $(OUTPUT_DIR_BLOCK)/code-block.pdf
INLINE_PDF := $(OUTPUT_DIR_INLINE)/code-inline.pdf

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

all: block inline

block: $(BLOCK_PDF)

$(BLOCK_PDF): code-block.md
	uv run texsmith $< -o$(OUTPUT_DIR_BLOCK) --build
	$(call copy_artifact,$@)

inline: $(INLINE_PDF)

$(INLINE_PDF): code-inline.md
	uv run texsmith $< -o$(OUTPUT_DIR_INLINE) --build
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR_BLOCK) $(OUTPUT_DIR_INLINE)

.PHONY: all clean block inline
