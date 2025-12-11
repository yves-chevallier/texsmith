include ../common.mk

DIN_ROOT := build_din
SN_ROOT := build_sn
NF_ROOT := build_nf

DIN_DIR := $(DIN_ROOT)/$(ENGINE)
SN_DIR := $(SN_ROOT)/$(ENGINE)
NF_DIR := $(NF_ROOT)/$(ENGINE)

DIN_PDF := $(DIN_DIR)/letter-din$(ENGINE_SUFFIX).pdf
SN_PDF := $(SN_DIR)/letter-sn$(ENGINE_SUFFIX).pdf
NF_PDF := $(NF_DIR)/letter-nf$(ENGINE_SUFFIX).pdf
DIN_BASE := $(DIN_DIR)/letter.pdf
SN_BASE := $(SN_DIR)/letter.pdf
NF_BASE := $(NF_DIR)/letter.pdf
ARTIFACTS := $(DIN_PDF) $(SN_PDF) $(NF_PDF)

$(DIN_DIR) $(SN_DIR) $(NF_DIR):
	mkdir -p "$@"

all: $(DIN_PDF) $(SN_PDF) $(NF_PDF)

$(DIN_PDF): letter.md marie-curie.svg | $(DIN_DIR)
	$(TEXSMITH) $< -o$(DIN_DIR) --build -tletter -aformat=din $(TEXSMITH_ENGINE)
	mv $(DIN_BASE) $(DIN_PDF)
	$(call copy_artifact,$@)

$(SN_PDF): letter.md marie-curie.svg | $(SN_DIR)
	$(TEXSMITH) $< -o$(SN_DIR) --build -tletter -aformat=sn $(TEXSMITH_ENGINE)
	mv $(SN_BASE) $(SN_PDF)
	$(call copy_artifact,$@)

$(NF_PDF): letter.md marie-curie.svg | $(NF_DIR)
	$(TEXSMITH) $< -o$(NF_DIR) --build -tletter -aformat=nf $(TEXSMITH_ENGINE)
	mv $(NF_BASE) $(NF_PDF)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_ROOT) $(DIN_ROOT) $(SN_ROOT) $(NF_ROOT)

.PHONY: all clean
