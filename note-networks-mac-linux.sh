#!/bin/bash
# Usage: ./note-networks-mac-linux.sh [network-name]
# Default network: aurelius
cd "$(dirname "$0")"
NETWORK="${1:-aurelius}"
python3 tools/watch.py "networks/$NETWORK"
