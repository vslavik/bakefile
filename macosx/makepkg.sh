#!/bin/sh

OLDPWD=$PWD
DELIVERDIR=deliver
BAKEFILEDIR=$PWD/..
BUILDROOT=bld-osx
INSTALLROOT=$PWD/$BUILDROOT/distrib
PREFIX=/usr/local
PYTHON=python
PROGDIR=$PWD

PRODUCT=Bakefile
VERSION="0.2.2"
PKGNAME="bakefile-$VERSION"

mkdir -p $INSTALLROOT/usr
cd $BUILDROOT
# this assumes the script is in a subdir 
$BAKEFILEDIR/configure --prefix=$PREFIX
make
make install DESTDIR=$INSTALLROOT

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
