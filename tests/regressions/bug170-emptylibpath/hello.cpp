#include <iostream>

#if defined(_WINDOWS)
#include <windows.h>
int WinMain(HINSTANCE, HINSTANCE, LPTSTR, int)
#else
int main()
#endif
{
    std::cout << "ok" << std::endl;
    return 0;
}
