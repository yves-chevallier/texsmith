OUTPUT_DIR := build

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

DIN_DIR := $(OUTPUT_DIR)/din
SN_DIR := $(OUTPUT_DIR)/sn
NF_DIR := $(OUTPUT_DIR)/nf

DIN_PDF := $(DIN_DIR)/letter-din.pdf
SN_PDF := $(SN_DIR)/letter-sn.pdf
NF_PDF := $(NF_DIR)/letter-nf.pdf

all: $(DIN_PDF) $(SN_PDF) $(NF_PDF)

$(DIN_PDF): letter.md marie-curie.svg
	uv run texsmith $< -o$(DIN_DIR) --build -tletter -aformat=din
	mv $(DIN_DIR)/letter.pdf $(DIN_PDF)
	$(call copy_artifact,$@)

$(SN_PDF): letter.md marie-curie.svg
	uv run texsmith $< -o$(SN_DIR) --build -tletter -aformat=sn
	mv $(SN_DIR)/letter.pdf $(SN_PDF)
	$(call copy_artifact,$@)

$(NF_PDF): letter.md marie-curie.svg
	uv run texsmith $< -o$(NF_DIR) --build -tletter -aformat=nf
	mv $(NF_DIR)/letter.pdf $(NF_PDF)
	$(call copy_artifact,$@)

clean:
	rm -rf $(OUTPUT_DIR)

.PHONY: all clean
