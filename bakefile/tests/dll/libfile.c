#include <stdio.h>

#ifdef WIN32
__declspec(dllexport)
#endif
void print()
{
    printf("hello, world!\n");
}
