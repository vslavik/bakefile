#!/bin/sh

aclocal -I admin
automake --foreign -a -c
autoconf
(cd doc ; ./process.sh)
