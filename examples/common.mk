.DEFAULT_GOAL := all
ENGINE ?= tectonic
OUTPUT_ROOT ?= build
ENGINE_DIR := $(OUTPUT_ROOT)/$(ENGINE)
ENGINE_SUFFIX := $(if $(filter $(ENGINE),tectonic),,$(addprefix -,$(ENGINE)))
TEXSMITH ?= uv run texsmith
TEXSMITH_ENGINE := $(if $(ENGINE),--engine=$(ENGINE),)

ifneq ($(strip $(ARTIFACTS_DIR)),)
copy_artifact = mkdir -p "$(ARTIFACTS_DIR)" && cp "$1" "$(ARTIFACTS_DIR)/"
else
copy_artifact = @true
endif

$(ENGINE_DIR):
	mkdir -p "$@"

.PHONY: tectonic lualatex xelatex

tectonic:
	$(MAKE) ENGINE=tectonic all

lualatex:
	$(MAKE) ENGINE=lualatex all

xelatex:
	$(MAKE) ENGINE=xelatex all
