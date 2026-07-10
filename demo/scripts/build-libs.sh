#!/usr/bin/env bash
# Builds the Python wheels and .NET nupkgs into demo/artifacts/.
# Java is built from source inside its Docker image, so it is not built here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ART="$ROOT/demo/artifacts"
mkdir -p "$ART"

echo "==> Building Python wheels (logs + traces)"
python -m pip install --quiet --upgrade build
( cd "$ROOT/libraries/python/logs" && python -m build --wheel --outdir "$ART" )
( cd "$ROOT/libraries/python/traces" && python -m build --wheel --outdir "$ART" )

echo "==> Building .NET nupkgs (logs + traces)"
( cd "$ROOT/libraries/dotnet/logs" && dotnet pack -c Release -o "$ART" )
( cd "$ROOT/libraries/dotnet/traces" && dotnet pack -c Release -o "$ART" )

echo "==> Artifacts in $ART:"
ls -1 "$ART"
