OUTPUT_ROOT := press
include ../common.mk

all:
	TEXSMITH_BUILD=1 uv run mkdocs build

clean:
	rm -rf press site

.PHONY: all clean
