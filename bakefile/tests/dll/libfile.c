#include <stdio.h>

#ifdef __WIN32__
__declspec(dllexport)
#endif
void print()
{
    printf("hello, world!\n");
}
