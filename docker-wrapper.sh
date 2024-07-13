#!/bin/bash

if [ "$1" = "bakefile" ] || [ "$1" = "bakefile_gen" ]; then
    CMD="$1"
    shift
else
    CMD=bakefile
fi

$CMD "$@"
