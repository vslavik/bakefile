# PYTHON_DEVEL()
#
# Checks for Python and tries to get the include path to 'Python.h'.
# It provides the $(PYTHON_CPPFLAGS) and $(PYTHON_LDFLAGS) output variable.
AC_DEFUN([BKL_PYTHON_DEVEL],[
	AC_REQUIRE([AM_PATH_PYTHON])

	# Check for Python include path
	AC_MSG_CHECKING([for Python include path])
	python_path=`${PYTHON} -c "from distutils import sysconfig; print sysconfig.get_python_inc()"`
	AC_MSG_RESULT([$python_path])
	if test -z "$python_path" ; then
		AC_MSG_ERROR([cannot find Python include path])
	fi
	AC_SUBST([PYTHON_CPPFLAGS],[-I$python_path])

	# Check for Python library path
	AC_MSG_CHECKING([for Python library path])
	python_ldflags=""
    if test "$PYTHON_PLATFORM" = "darwin" ; then
        py_framework=`${PYTHON} -c "import sys; print sys.prefix.find('/Frameworks/')"`
        if test "x$py_framework" != "x-1" ; then
            python_ldflags="-framework Python"
            python_path="framework"
        fi
    fi
    # Apple's Python not found, try standard search:
    if test -z "$python_ldflags" ; then
        python_path=${PYTHON%/bin*}
        for i in "$python_path/lib/python$PYTHON_VERSION/config/" "$python_path/lib/python$PYTHON_VERSION/" "$python_path/lib/python/config/" "$python_path/lib/python/" "$python_path/" ; do
            python_path=`find $i -type f -name "libpython$PYTHON_VERSION.*" -print | head -n 1 2>/dev/null`
            if test -n "$python_path" ; then
                break
            fi
        done
        for i in $python_path ; do
            python_path=${python_path%/libpython*}
            break
        done
    	if test "x$python_path" != "x" ; then
            python_ldflags="-L$python_path -lpython$PYTHON_VERSION"
        fi
    fi
	AC_MSG_RESULT([$python_path])
	if test -z "$python_ldflags" ; then
		AC_MSG_ERROR([cannot find Python library path])
	fi
	AC_SUBST([PYTHON_LDFLAGS],[$python_ldflags])
])
