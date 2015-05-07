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
// otherwise the constant won't be present when cffi loads.
// NOTE: These are defined here rather than in the Python modules
//       because it prevents someone from accidentally overriding
//       the value.  Attempting to assign to one of these values
//       in the interpreter will raise an exception at runtime.
#define ERROR_FILE_NOT_FOUND 0x2
#define ERROR_PATH_NOT_FOUND 0x3
#define ERROR_ACCESS_DENIED 0x5
#define ERROR_INVALID_HANDLE 0x6
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
#define MAX_PATH 32767
#define READ_CONTROL 0x00020000
#define STANDARD_RIGHTS_READ 0x00020000
#define STANDARD_RIGHTS_WRITE 0x00020000
#define STANDARD_RIGHTS_EXECUTE 0x00020000
#define FILE_READ_DATA 0x1
#define FILE_READ_ATTRIBUTES 0x80
#define FILE_READ_EA 0x8
#define SYNCHRONIZE 0x100000
#define STANDARD_RIGHTS_ALL 0x001F0000
#define SPECIFIC_RIGHTS_ALL 0x0000FFFF
#define FILE_WRITE_DATA 0x2
#define FILE_WRITE_ATTRIBUTES 0x100
#define FILE_WRITE_EA 0x20
#define FILE_EXECUTE 0x20


// Define functions which Twisted will be using either internally
// or in tests.
// NOTE: Functions exposed should support Windows XP and up. Even though
// XP support has been dropped there's still a large install base out there
// with XP.
HANDLE OpenProcess(DWORD, BOOL, DWORD);
BOOL CreatePipe(PHANDLE, PHANDLE, LPSECURITY_ATTRIBUTES, DWORD);
BOOL PeekNamedPipe(HANDLE, LPVOID, DWORD, LPDWORD, LPDWORD, LPDWORD);
BOOL CloseHandle(HANDLE);
BOOL ReadFile(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
BOOL WriteFile(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);
BOOL SetNamedPipeHandleState(HANDLE, LPDWORD, LPDWORD, LPDWORD);
DWORD GetTempPathW(DWORD, LPTSTR);
DWORD GetTempPathA(DWORD, LPTSTR);
UINT GetTempFileNameW(LPCTSTR, LPCTSTR, UINT, LPTSTR);
UINT GetTempFileNameA(LPCTSTR, LPCTSTR, UINT, LPTSTR);
HANDLE CreateFileW(
    LPCTSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
HANDLE CreateFileA(
    LPCTSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
