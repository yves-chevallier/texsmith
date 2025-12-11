.DEFAULT_GOAL := all
.SECONDEXPANSION:
ENGINE ?= tectonic
OUTPUT_ROOT ?= build
ENGINE_DIR := $(OUTPUT_ROOT)/$(ENGINE)
ENGINE_SUFFIX := $(if $(filter $(ENGINE),tectonic),,$(addprefix -,$(ENGINE)))
TEXSMITH ?= uv run texsmith
TEXSMITH_ENGINE := $(if $(ENGINE),--engine=$(ENGINE),)
ARTIFACTS ?= $(PDF)

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
ARTIFACT_TARGETS = $(foreach artifact,$(strip $(ARTIFACTS)),$(ARTIFACTS_DIR)/$(notdir $(artifact)))
define find_artifact_for_basename
$(strip $(filter %/$(1),$(ARTIFACTS)))
endef
else
copy_artifact = @true
endif

$(ENGINE_DIR):
	mkdir -p "$@"

ifneq ($(strip $(ARTIFACTS_DIR)),)
# Use second expansion so artifacts registered after including this file
# are still attached to the `all` target.
all: $$(ARTIFACT_TARGETS)

$(ARTIFACTS_DIR)/%: $$(call find_artifact_for_basename,$$*) | $(ARTIFACTS_DIR)
	cp "$<" "$@"

$(ARTIFACTS_DIR):
	mkdir -p "$@"
endif

.PHONY: tectonic lualatex xelatex

tectonic:
	$(MAKE) ENGINE=tectonic all

lualatex:
	$(MAKE) ENGINE=lualatex all

xelatex:
	$(MAKE) ENGINE=xelatex all
