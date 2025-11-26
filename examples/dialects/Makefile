OUTPUT_DIR := build

all: dialects.md
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle
latex: dialects.md
	uv run texsmith $< -o$(OUTPUT_DIR) -tarticle
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean
