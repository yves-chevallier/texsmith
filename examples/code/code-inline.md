# Inline Code

In C the `strstr` function defined with the prototype
`#!c char *strstr(const char *haystack, const char *needle);` is
used to locate a substring within a string. It returns a pointer to the first occurrence of the substring
`needle` in the string `haystack`, or `NULL` if the substring is not found.

In Python, you can achieve similar functionality using the `find` method of strings for example: `#!python haystack.find(sub: int) -> int`. This method returns the lowest index of the substring if found in the string, otherwise it returns `-1`.
