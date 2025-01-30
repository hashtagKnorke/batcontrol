#!/bin/sh
# This script installs the required Alpine Linux modules for specific plugins.
# It determines the required packages by looking into the manifest.yaml files
# located in the specified plugin directory. The script parses
# these manifest files to extract the list of necessary Alpine packages
# and then installs them using the apk package manager.
set -e

# Check if the plugin directory is provided as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 <plugin_directory>"
  exit 1
fi

PLUGIN_DIR=$1

# Iterate over all manifest.yaml files and collect required_alpine_packages
REQUIRED_PACKAGES=""
for manifest in $(find "$PLUGIN_DIR" -name "manifest.yaml"); do
  echo "Processing manifest: $manifest"
  PACKAGES=$(yq e '.required_alpine_packages[]' "$manifest")
  REQUIRED_PACKAGES="$REQUIRED_PACKAGES $PACKAGES"
done

# Remove duplicate packages
REQUIRED_PACKAGES=$(echo "$REQUIRED_PACKAGES" | tr ' ' '\n' | sort -u | tr '\n' ' ')

# Install required alpine packages
if [ -n "$REQUIRED_PACKAGES" ]; then
  echo "Installing required Alpine packages: $REQUIRED_PACKAGES"
  apk add --no-cache $REQUIRED_PACKAGES
fi
