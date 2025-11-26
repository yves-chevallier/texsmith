OUTPUT_DIR := build

all: cheese.md cheese.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
latex: cheese.md cheese.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean
