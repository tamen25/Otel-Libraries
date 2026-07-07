#!/usr/bin/env bash
# Builds the Python wheel and .NET nupkg into demo/artifacts/.
# Java is built from source inside its Docker image, so it is not built here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ART="$ROOT/demo/artifacts"
mkdir -p "$ART"

echo "==> Building Python wheel"
python -m pip install --quiet --upgrade build
( cd "$ROOT/libraries/python/logs" && python -m build --wheel --outdir "$ART" )

echo "==> Building .NET nupkg"
( cd "$ROOT/libraries/dotnet/logs" && dotnet pack -c Release -o "$ART" )

echo "==> Artifacts in $ART:"
ls -1 "$ART"
