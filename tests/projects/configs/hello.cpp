#include <stdio.h>

extern const char *helper_name();

int main()
{
  printf("Hello from %s\n", helper_name());
  return 0;
}