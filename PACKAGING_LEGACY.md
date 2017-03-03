
See `build/` SCons files for how to build from scratch. At this time, that
doesn't make much sense to do anymore, though. This file documents how to
re-package things if necessary.

 macOS
=======

1. Download latest `.pkg` and unpack it into some ROOT directory (with
   `usr/local` content under it).

2. Change any files that need it.

3. Re-build the package:
    ```
    productbuild --content ROOT \
                 --identifier org.bakefile.Bakefile --version $version \
                 --sign 'Developer ID' --timestamp Bakefile-$version.pkg
    ```

 Windows
=========

1. Install latest release

2. Copy `.pyd` and `.exe` files from root and `src/` to the same location
   in source tree.

3. Copy `lib` and Python files (including MSVC runtime DLL) into `py-runtime`.

4. Use Inno Setup.
