/*
 *  This file is part of Bakefile (http://www.bakefile.org)
 *
 *  Copyright (C) 2003-2007 Vaclav Slavik
 *
 *  Permission is hereby granted, free of charge, to any person obtaining a
 *  copy of this software and associated documentation files (the "Software"),
 *  to deal in the Software without restriction, including without limitation
 *  the rights to use, copy, modify, merge, publish, distribute, sublicense,
 *  and/or sell copies of the Software, and to permit persons to whom the
 *  Software is furnished to do so, subject to the following conditions:
 *
 *  The above copyright notice and this permission notice shall be included in
 *  all copies or substantial portions of the Software.
 *
 *  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 *  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 *  DEALINGS IN THE SOFTWARE.
 *
 *  $Id$
 *
 *  This is only a simple script-launcher utility that calls Python
 *  interpreter on win32 systems, so that running the tools is simpler.
 *
 */

#include <string.h>
#include <stdio.h>
#include <Python.h>
#include <malloc.h>
#include <stdlib.h>
#include <windows.h>


/* directory where to look for .py file, relative to .exe location: */
#define SCRIPT_DIRECTORY    "src\\"


int IsPythonEmbedded(const char *dirname)
{
    char dllname[2048];
    sprintf(dllname, "%spython%i%i.dll", dirname,
            PY_MAJOR_VERSION, PY_MINOR_VERSION);
    puts(dllname);
    return _access(dllname, 0) == 0;
}


/* ----------------------------------------------------------------------- */
/*       main() - sets PYTHONHOME and calls PyRun_SimpleFile on            */
/*               script with same name but .py extension                   */
/* ----------------------------------------------------------------------- */

int main(int argc, char** argv)
{
    int ret;
    char exename[2048];
    char filename[2048];
    char dirname[2048];
    char basename[2048];
    char envvar[2048];
    FILE *fp;
    char *lastp = NULL;

    strncpy(exename, argv[0], 2048);
    if (GetModuleFileName(NULL, (char*)exename, 2048) != 0)
    {
        lastp = strrchr(exename, '\\');
        if (lastp == NULL)
        {
            strncpy(dirname, ".\\", 2048);
            strncpy(basename, exename, 2048);
        }
        else
        {
            strncpy(dirname, exename, lastp - exename + 1);
            dirname[lastp - exename + 1] = 0;
            strncpy(basename, lastp+1, 2048);
        }

        lastp = strrchr(basename, '.');
    }
    if (lastp == NULL)
    {
        fprintf(stderr, "Incorrect executable name!\n");
        return 1;
    }

    strncpy(lastp, ".py", 2048-(2+lastp-basename));


    strncpy(filename, dirname, 2048);
    strncat(filename, SCRIPT_DIRECTORY, 2048 - strlen(filename));
    strncat(filename, basename, 2048 - strlen(filename));


    fp = fopen(filename, "rb");
    if (fp == NULL)
    {
        fprintf(stderr, "Cannot open script file '%s'!\n", filename);
        return 2;
    }

    if ( IsPythonEmbedded(dirname) )
    {
        puts("embedding");
        /* set PYTHONHOME so that system-wide installed copy of Python is
           never used; we want to use embedded one: */
        SetEnvironmentVariable("PYTHONHOME", dirname);
        sprintf(envvar, "PYTHONHOME=%s", dirname);
        _putenv(envvar);

        /* ditto with PYTHONPATH, but make it empty: */
        SetEnvironmentVariable("PYTHONPATH", "");
        _putenv("PYTHONPATH=");
    }

    Py_Initialize();
    argv[0] = (char*)filename;
    PySys_SetArgv(argc, argv);
    ret = PyRun_SimpleFile(fp, filename);
    Py_Finalize();
    fclose(fp);

    if (ret != 0)
        fprintf(stderr, "Error executing the script!\n");
    return ret;
}
