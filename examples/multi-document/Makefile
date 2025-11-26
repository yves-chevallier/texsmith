OUTPUT_DIR := build

all: a.md b.md c.md config.yml
	uv run texsmith $^ -o$(OUTPUT_DIR) --build -tarticle
latex: a.md b.md c.md config.yml
	uv run texsmith $^ -o$(OUTPUT_DIR) -tarticle
clean:
	rm -rf $(OUTPUT_DIR)
.PHONY: all clean
