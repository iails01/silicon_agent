#!/bin/bash
# Build sandbox container images for silicon_agent.
#
# Usage:
#   cd platform
#   bash sandbox/build.sh [base|coding|test|all]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PLATFORM_DIR"

build_base() {
    echo "==> Building silicon-agent-sandbox:base"
    docker build -t silicon-agent-sandbox:base -f sandbox/Dockerfile.base .
}

build_coding() {
    echo "==> Building silicon-agent-sandbox:coding"
    docker build -t silicon-agent-sandbox:coding -f sandbox/Dockerfile.coding .
}

build_test() {
    echo "==> Building silicon-agent-sandbox:test"
    docker build -t silicon-agent-sandbox:test -f sandbox/Dockerfile.test .
}

TARGET="${1:-all}"

case "$TARGET" in
    base)
        build_base
        ;;
    coding)
        build_base
        build_coding
        ;;
    test)
        build_base
        build_coding
        build_test
        ;;
    all)
        build_base
        build_coding
        build_test
        ;;
    *)
        echo "Usage: $0 [base|coding|test|all]"
        exit 1
        ;;
esac

echo ""
echo "==> Built images:"
docker images --filter "reference=silicon-agent-sandbox" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
