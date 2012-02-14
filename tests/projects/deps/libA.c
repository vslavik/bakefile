#include <stdio.h>

// from libcommon:
extern const char* get_version_info();
extern const char* get_os_name();

void print_A_banner()
{
    printf("library A, version %s running on %s\n", get_version_info(), get_os_name());
}
