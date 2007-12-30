#include <stdio.h>

#ifndef SOMETHING
    #error "SOMETHING must be defined"
#endif

#ifndef MESSAGE
    #define MESSAGE "generic"
#endif

int main()
{
    printf("Hello, world (" MESSAGE ")!\n");
    return 0;
}
