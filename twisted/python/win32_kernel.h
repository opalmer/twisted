/*
 * Copyright (c) Twisted Matrix Laboratories.
 * See LICENSE for details.
 */

typedef struct _SECURITY_ATTRIBUTES {
  DWORD  nLength;
  LPVOID lpSecurityDescriptor;
  BOOL   bInheritHandle;
} SECURITY_ATTRIBUTES, *PSECURITY_ATTRIBUTES, *LPSECURITY_ATTRIBUTES;

typedef struct _OVERLAPPED {
  ULONG_PTR Internal;
  ULONG_PTR InternalHigh;
  union {
    struct {
      DWORD Offset;
      DWORD OffsetHigh;
    };
    PVOID  Pointer;
  };
  HANDLE    hEvent;
} OVERLAPPED, *LPOVERLAPPED;



// Define constants which will be present on the win32 object
// we create.  Note that you must define constants using
// the values here rather than
//      #define SOME_CONSTANT ...
// otherwise the constant won't be present
#define ERROR_FILE_NOT_FOUND 0x2
#define ERROR_PATH_NOT_FOUND 0x3
#define ERROR_ACCESS_DENIED 0x5
#define ERROR_INVALID_PARAMETER 0x57
#define ERROR_INVALID_NAME 0x7B
#define ERROR_DIRECTORY 0x10B
#define FILE_FLAG_OVERLAPPED 0x40000000
#define FILE_APPEND_DATA 4
#define ERROR_IO_PENDING 997
#define PIPE_READMODE_BYTE 0x00000000
#define PIPE_READMODE_MESSAGE 0x00000002
#define PIPE_WAIT 0x00000000
#define PIPE_NOWAIT 0x00000001



// Define functions which Twisted will be using either internally
// or in tests.
HANDLE OpenProcess(DWORD, BOOL, DWORD);
BOOL CreatePipe(PHANDLE, PHANDLE, LPSECURITY_ATTRIBUTES, DWORD);
BOOL PeekNamedPipe(HANDLE, LPVOID, DWORD, LPDWORD, LPDWORD, LPDWORD);
BOOL CloseHandle(HANDLE);
BOOL ReadFile(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
BOOL WriteFile(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);
BOOL SetNamedPipeHandleState(HANDLE, LPDWORD, LPDWORD, LPDWORD);
