/*
 * Copyright (c) Twisted Matrix Laboratories.
 * See LICENSE for details.
 */

typedef struct _SECURITY_ATTRIBUTES {
  DWORD  nLength;
  LPVOID lpSecurityDescriptor;
  BOOL   bInheritHandle;
} SECURITY_ATTRIBUTES, *PSECURITY_ATTRIBUTES, *LPSECURITY_ATTRIBUTES;


// Define constants which will be present on the win32 object
// we create.  Note that you must define constants using
// the values here rather than
//      #define SOME_CONSTANT ...
// otherwise the constant won't be present
#define _O_BINARY 0x8000
#define ERROR_FILE_NOT_FOUND 0x2
#define ERROR_PATH_NOT_FOUND 0x3
#define ERROR_ACCESS_DENIED 0x5
#define ERROR_INVALID_PARAMETER 0x57
#define ERROR_INVALID_NAME 0x7B
#define ERROR_DIRECTORY 0x10B

HANDLE OpenProcess(DWORD, BOOL, DWORD);
BOOL CreatePipe(PHANDLE, PHANDLE, LPSECURITY_ATTRIBUTES, DWORD);
