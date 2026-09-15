#set page(margin: 2.5cm)
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true)

#ts-callout-style.update("fancy")

= Inline Code

In C the `strstr` function defined with the prototype
#raw(lang: "c", "char *strstr(const char *haystack, const char *needle);") is
used to locate a substring within a string. It returns a pointer to the first occurrence of the substring
`needle` in the string `haystack`, or `NULL` if the substring is not found.

In Python, you can achieve similar functionality using the `find` method of strings for example: #raw(lang: "python", "haystack.find(sub: int) -> int"). This method returns the lowest index of the substring if found in the string, otherwise it returns `-1`.
