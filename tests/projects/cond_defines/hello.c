#include <stdio.h>

int main()
{
    printf("Hello, world!\n");
#ifdef PRINT_DETAILS
    #ifdef PLATFORM_UNIX
        printf("(on Unix)\n");
    #endif
    #ifdef PLATFORM_WINDOWS
        printf("(on Windows)\n");
    #endif
#endif
    return 0;
}
