#!/usr/bin/env bash

set -e

echo "🚨 FALLBACK MODE ACTIVATED"

if ! command -v node >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y nodejs npm
fi

if ! command -v jules >/dev/null 2>&1; then
    npm install -g @google/jules
fi

echo "✅ fallback ready"
