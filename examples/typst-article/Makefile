TEXSMITH ?= uv run texsmith
OUTPUT_DIR ?= build
TYP := $(OUTPUT_DIR)/article.typ

all: $(TYP)

# Emit the standalone .typ via the Typst backend (HTML -> IR -> Typst).
$(TYP): article.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< --format typst -o $(OUTPUT_DIR)

# Compile to PDF when the `typst` binary is available (graceful otherwise).
pdf: article.md | $(OUTPUT_DIR)
	$(TEXSMITH) $< --format typst -o $(OUTPUT_DIR) --build

# `typst` alias so the aggregate `make typst` at the examples root is uniform.
typst: pdf

$(OUTPUT_DIR):
	mkdir -p "$@"

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all pdf typst clean
