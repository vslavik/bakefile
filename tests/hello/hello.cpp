#include <iostream>
#include "hello.h"

#if defined(BUILD_AS_GUI) && defined(_WINDOWS)
#include <windows.h>
int WinMain(HINSTANCE, HINSTANCE, LPSTR, int)
#else
int main()
#endif
{
    std::cout << HELLO_BANNER << std::endl;
    return 0;
}
