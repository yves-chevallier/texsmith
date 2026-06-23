TEXSMITH ?= uv run texsmith
OUTPUT_DIR ?= build
TYP := $(OUTPUT_DIR)/hello.typ

all: $(TYP)

# Emit the standalone .typ via the Typst backend (HTML -> IR -> Typst).
$(TYP): hello.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< --format typst -o $(OUTPUT_DIR)

# Compile to PDF when the `typst` binary is available (graceful otherwise).
pdf: hello.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< --format typst -o $(OUTPUT_DIR) --build

$(OUTPUT_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all pdf clean
