OUTPUT_DIR := build

all: booby.md booby.png
	uv run texsmith $< -o$(OUTPUT_DIR) --build -tarticle
latex: booby.md booby.png
	uv run texsmith $< -o$(OUTPUT_DIR) -tarticle
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean
