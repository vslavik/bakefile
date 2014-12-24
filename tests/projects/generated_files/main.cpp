#include <stdio.h>
#include "gensrc.h"
#include "gensrc2.h"

int main()
{
    printf("first generated file contents is \"%s\"\n", get_gensrc_body());
    printf("second generated file contents is \"%s\"\n", get_gensrc2_body());
    return 0;
}
