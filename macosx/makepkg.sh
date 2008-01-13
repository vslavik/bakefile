#!/bin/sh

OLDPWD=$PWD
DELIVERDIR=deliver
BAKEFILEDIR=$PWD/..
BUILDROOT=bld-osx
INSTALLROOT=$PWD/$BUILDROOT/distrib
PREFIX=/usr/local
PROGDIR=$PWD
PYTHON=python

PRODUCT=Bakefile
VERSION="0.2.3"
PKGNAME="Bakefile"
DMGNAME="bakefile-$VERSION"

mkdir -p $INSTALLROOT/usr
cd $BUILDROOT
# this assumes the script is in a subdir
$BAKEFILEDIR/configure \
            --prefix=$PREFIX \
            --disable-dependency-tracking
make || exit 1
make install DESTDIR=$INSTALLROOT || exit 1

pydir=$INSTALLROOT$PREFIX/lib/bakefile
bindir=$INSTALLROOT$PREFIX/bin

# remove _bottlenecks module and rebuild it for all target archs and versions
rm -rf $pydir/_bottlenecks*

build_with_sdk()
{
    sdk="$1"
    sdkdir="/Developer/SDKs/MacOSX${sdk}.sdk"
    osxver="$2"
    pyver="$3"
    archs="$4"
    outdir="$pydir/binmodules/$pyver"

    if [ -d $sdkdir ] ; then
        export MACOSX_DEPLOYMENT_TARGET="$osxver"
        flags="-O2 -isysroot $sdkdir"
        for a in $archs ; do
            flags="$flags -arch $a"
        done
        flags="$flags -I$sdkdir/System/Library/Frameworks/Python.framework/Headers"
        mkdir -p $outdir
        gcc -bundle -undefined dynamic_lookup \
            -o $outdir/_bottlenecks.so $flags \
            $BAKEFILEDIR/src/bottlenecks.c \
            $BAKEFILEDIR/src/bottlenecks_wrap.c \
            || exit 1
    fi
}

build_with_sdk "10.4u"  "10.4"  "2.3"  "ppc i386"
build_with_sdk "10.5"   "10.5"  "2.5"  "ppc i386 ppc64 x86_64"

if [ -n "$EXTRA_BINMODULES" ] ; then
    (cd $EXTRA_BINMODULES ; tar c .) | (cd $pydir/binmodules ; tar x)
fi

# install wrapper to make using this build possible:
rm -rf $bindir/bakefile
rm -rf $bindir/bakefile_gen
sed -e "s,@prefix@,$PREFIX,g" $BAKEFILEDIR/macosx/bakefile-wrapper >$pydir/bakefile-wrapper
chmod +x $pydir/bakefile-wrapper
ln -s ../lib/bakefile/bakefile-wrapper $bindir/bakefile
ln -s ../lib/bakefile/bakefile-wrapper $bindir/bakefile_gen


# now build installer package
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

mkdir -p $DMGNAME
rm -rf $DMGNAME/*

mv $PKGNAME.pkg $DMGNAME

DMG_NAME=$DMGNAME.dmg
if [ -f $DMG_NAME ]; then
   rm $DMG_NAME
fi
     
hdiutil create -srcfolder $DMGNAME -volname "$DMGNAME" -imagekey zlib-level=9 $DMG_NAME

rm -rf $BUILDROOT
rm -rf $DMGNAME

# end script
