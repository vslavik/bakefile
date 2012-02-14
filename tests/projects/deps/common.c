
#ifdef _WIN32
  #include <windows.h>
  #include <wininet.h>
#else
  #include <iconv.h>
#endif

static char buf[2048];

const char *get_os_name()
{
#ifdef _WIN32
    // this is just to force dependency on some external library
    int i = (int)&InternetOpenUrl;
    return i % 2 ? "Windows" : "Microsoft Windows";
#else
    // this is just to force dependency on some external library
    int i = (int)&iconv_open;
    return i % 2 ? "some Unix" : "some UNIX";
#endif
}

const char* get_version_info()
{
    return "1.0";
}
