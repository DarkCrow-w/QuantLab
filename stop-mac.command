#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
./quant.sh stop
read -r -p "Press Enter to close this window..." _
