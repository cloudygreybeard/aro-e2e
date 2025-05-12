IMAGE_NAME := test-image
TAG := latest
ARCHIVE := $(IMAGE_NAME)-oci.tar
CONFIGMAP_NAME := $(IMAGE_NAME)-oci
CONFIGMAP_FILE := $(CURDIR)/../configmap.$(CONFIGMAP_NAME).json

.PHONY: all build save configmap clean

all: configmap

build:
	# Build the container image
	podman build -t $(IMAGE_NAME):$(TAG) .

save: build
	# Obtain an OCI-formatted archive of the built image
	podman image save --format oci-archive -o $(ARCHIVE) $(IMAGE_NAME):$(TAG)

configmap: save
	# Create the ConfigMap using jq, base64 encoding the tarball content inline
	@jq -sRn --arg name '$(CONFIGMAP_NAME)' --arg filename '$(ARCHIVE)' '{"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":$$name},"binaryData":{($$filename):(inputs|@base64)}}' < $(ARCHIVE) > $(CONFIGMAP_FILE)
	@echo "Wrote ConfigMap to $(CONFIGMAP_FILE)"
	@rm -f $(ARCHIVE)

clean:
	rm -f $(ARCHIVE) $(CONFIGMAP_FILE)
