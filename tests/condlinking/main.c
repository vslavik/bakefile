
#ifdef LINK_AGAINST_LIB
extern void hello();
#else
#include "hello.c"
#endif


int main()
{
    hello();
    return 0;
}
