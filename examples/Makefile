export ARTIFACTS_DIR := ./examples_build

all: $(OUTPUT_DIR)
	$(MAKE) -C abbr/ all
	$(MAKE) -C booby/ all
	$(MAKE) -C admonition/ all

tectonic: $(OUTPUT_DIR)
	$(MAKE) -C abbr/ tectonic
	$(MAKE) -C booby/ tectonic
	$(MAKE) -C admonition/ tectonic

clean:
	$(RM) -rf $(OUTPUT_DIR)
	$(MAKE) -C abbr/ clean
	$(MAKE) -C booby/ clean
	$(MAKE) -C admonition/ clean

$(OUTPUT_DIR):
	mkdir -p $@

.PHONY: all clean tectonic
