#!/usr/bin/env bash
# Build the extension and copy it next to this script.
#
#   ./build.sh   -> PolyKybdContextReporter.bwextension
#
# Needs a JDK (11 or later) and Maven. The Bitwig API jar comes from
# https://maven.bitwig.com (pom.xml). A .bwextension is the jar under another
# name. Install: see README.md.
set -euo pipefail
cd "$(dirname "$0")"
mvn -q -B package
cp target/PolyKybdContextReporter.jar PolyKybdContextReporter.bwextension
echo "built $(pwd)/PolyKybdContextReporter.bwextension"
