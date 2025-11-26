export ARTIFACTS_DIR := ./examples_build

all:
	$(MAKE) -C booby/ all
	$(MAKE) -C admonition/ all

tectonic:
	$(MAKE) -C booby/ tectonic
	$(MAKE) -C admonition/ tectonic

clean:
	$(MAKE) -C booby/ clean
	$(MAKE) -C admonition/ clean

$(OUTPUT_DIR):
	mkdir -p $@

.PHONY: all clean tectonic
