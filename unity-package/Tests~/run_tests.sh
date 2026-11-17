#!/usr/bin/env bash
# Build and run the package's tests without Unity (Mono: apt install mono-mcs mono-runtime).
#  1. ReporterCore.cs + CoreTests.cs -> run the unit tests.
#  2. The whole Editor/ folder against UnityStubs.cs -> a compile check of the
#     Unity glue. The stubs are not Unity's assemblies (see UnityStubs.cs).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
src="$here/../Editor"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
mcs -langversion:7.2 -warnaserror -nologo -out:"$out/core_tests.exe" \
    "$src/ReporterCore.cs" "$here/CoreTests.cs"
mono "$out/core_tests.exe"
mcs -langversion:7.2 -warnaserror -nologo -define:UNITY_2023_2_OR_NEWER -target:library \
    -out:"$out/glue.dll" "$src"/*.cs "$here/UnityStubs.cs"
mcs -langversion:7.2 -warnaserror -nologo -target:library \
    -out:"$out/glue_old.dll" "$src"/*.cs "$here/UnityStubs.cs"
echo "Editor glue compiles against the stubs (with and without UNITY_2023_2_OR_NEWER)"
