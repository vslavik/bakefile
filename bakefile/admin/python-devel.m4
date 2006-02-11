# PYTHON_DEVEL()
#
# Checks for Python and tries to get the include path to 'Python.h'.
# It provides the $(PYTHON_CPPFLAGS) output variable.
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
])
