#!/bin/sh

set -e

make -C ..

cd pyinstaller
rm -rf _extras
mkdir -p _extras/antlr3
cp -a ../../3rdparty/antlr3/runtime/Python/antlr3/*.py _extras/antlr3
python ../../3rdparty/pyinstaller/pyinstaller.py -p _extras bkl.spec
rm -rf _extras
cd ..

cd wix
candle bkl.wxs
light -ext WixUIExtension bkl.wixobj
cd ..
