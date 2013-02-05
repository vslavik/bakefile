#include <stdio.h>

int main()
{
  #ifdef DEFAULT_NAME
    #define REMARK " (default)"
  #else
    #define REMARK ""
  #endif
  printf("Hello from %s" REMARK "!\n", PROGRAM_NAME);
  return 0;
}
