#!/bin/sh

aclocal-1.6 -I admin
automake-1.6 --foreign -a -c
autoconf
