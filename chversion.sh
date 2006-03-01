#!/bin/sh

replace_ver()
{
    echo "
,s@$2@$3@g
w
q
" | ed -s $1 2>/dev/null
}

VER=$1

replace_ver bakefile.spec \
            '\(Version: *\).*' "\1$VER"
replace_ver bakefile.iss \
            '\(#define VERSION *"\).*\("\)' "\1$VER\2"
replace_ver configure.in \
            '\(AC_INIT(\[bakefile\], \[\)[^]]*\(\],.*\)' "\1$VER\2"
replace_ver src/bakefile.py \
            '\(BAKEFILE_VERSION = "\).*\("\)' "\1$VER\2"
replace_ver rules/version.bkl \
            '\(>\).*\(<\)' "\1$VER\2"
replace_ver autoconf/bakefile.m4 \
            '\(BAKEFILE_BAKEFILE_M4_VERSION="*\).*\("\)' "\1$VER\2"
