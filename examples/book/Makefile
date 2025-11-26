OUTPUT_DIR := build

all: book.md book.bib
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -abibliography_style=numeric || true
	cd $(OUTPUT_DIR) && biber book
	cd $(OUTPUT_DIR) && latexmk -lualatex book.tex
clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
