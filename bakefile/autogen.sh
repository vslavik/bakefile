#!/bin/sh

mkdir -p admin
aclocal -I admin
libtoolize --automake -c -f
automake --foreign -a -c
autoconf
(cd src ; swig -python bottlenecks.i)
(cd doc ; ./process.sh)
