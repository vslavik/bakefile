#include <stdio.h>

// this header file is used just to test
// the header (un)install bakefile support
#include "hello.h"

int main()
{
    func("Hello, world!\n");
    return 0;
}


// we need to export at least a function to have
// some toolchains like MSVC's nmake generate
// the import library (without which the 'install' 
// target will fail!)
#ifdef MAKING_THE_DLL

#    if defined(WIN32) && (defined(_MSC_VER) || defined(__BORLANDC__) || defined(__GNUC__) || defined(__WATCOMC__))
#        define EXPORT __declspec(dllexport)
#        define IMPORT __declspec(dllimport)
#    else /* compiler doesn't support __declspec() */
#        define EXPORT
#        define IMPORT
#        error The import library won't be created
#    endif

void EXPORT doReallyNothing()
{
   printf("Have fun with this function!\n");
}

#endif
