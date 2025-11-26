OUTPUT_DIR := build

all: book.md book.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) --build
clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
