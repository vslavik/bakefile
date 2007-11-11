#!/bin/sh

OSX_SDK="/Developer/SDKs/MacOSX10.4u.sdk"
OSX_PYTHON_VER="2.3"

OLDPWD=$PWD
DELIVERDIR=deliver
BAKEFILEDIR=$PWD/..
BUILDROOT=bld-osx
INSTALLROOT=$PWD/$BUILDROOT/distrib
PREFIX=/usr/local
PROGDIR=$PWD

PYTHON="/System/Library/Frameworks/Python.framework/Versions/$OSX_PYTHON_VER/bin/python"
UNIV_BIN_FLAGS="-isysroot $OSX_SDK -arch ppc -arch i386"

PRODUCT=Bakefile
VERSION="0.2.2"
PKGNAME="bakefile-$VERSION"

mkdir -p $INSTALLROOT/usr
cd $BUILDROOT
# this assumes the script is in a subdir
$BAKEFILEDIR/configure \
            --prefix=$PREFIX \
            CFLAGS="$UNIV_BIN_FLAGS" \
            LDFLAGS="$UNIV_BIN_FLAGS" \
            PYTHON=$PYTHON \
            --disable-dependency-tracking
make -k
make install DESTDIR=$INSTALLROOT -k

cd $OLDPWD

rm -rf $PKGNAME.pkg
$PYTHON $PROGDIR/buildpkg.py \
	--Title="$PKGNAME" \
	--Version="$VERSION" \
	--Description="$PRODUCT $VERSION for OS X." \
	--NeedsAuthorization="YES" \
	--Relocatable="NO" \
	--InstallOnly="YES" \
	$INSTALLROOT

mkdir -p $PKGNAME
rm -rf $PKGNAME/*

mv $PKGNAME.pkg $PKGNAME

DMG_NAME=$PKGNAME.dmg
if [ -f $DMG_NAME ]; then
   rm $DMG_NAME
fi
     
hdiutil create -srcfolder $PKGNAME -volname "$PKGNAME" -imagekey zlib-level=9 $DMG_NAME

rm -rf $BUILDROOT
rm -rf $PKGNAME

# end script
