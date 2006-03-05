#include <iostream>

#if defined(BUILD_AS_GUI) && defined(_WINDOWS)
#include <windows.h>
int WinMain(HINSTANCE, HINSTANCE, LPSTR, int)
#else
int main()
#endif
{
    std::cout << "Hello, world!" << std::endl;
    return 0;
}
