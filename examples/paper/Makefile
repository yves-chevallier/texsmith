all: cheese.md cheese.bib
	uv run texsmith $^ -obuild --build -tarticle
clean:
	rm -rf build
.PHONY: all clean
