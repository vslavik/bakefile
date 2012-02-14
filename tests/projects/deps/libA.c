#include <stdio.h>

// from libcommon:
extern const char* get_version_info();

void print_A_banner()
{
    printf("library A, version %s\n", get_version_info());
}
