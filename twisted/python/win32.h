/*
 * Copyright (c) Twisted Matrix Laboratories.
 * See LICENSE for details.
 */

typedef struct {
    DWORD  nLength;
    LPVOID lpSecurityDescriptor;
    BOOL   bInheritHandle;
} SECURITY_ATTRIBUTES, *PSECURITY_ATTRIBUTES, *LPSECURITY_ATTRIBUTES;

typedef struct {
    DWORD  cb;
    LPTSTR lpReserved;
    LPTSTR lpDesktop;
    LPTSTR lpTitle;
    DWORD  dwX;
    DWORD  dwY;
    DWORD  dwXSize;
    DWORD  dwYSize;
    DWORD  dwXCountChars;
    DWORD  dwYCountChars;
    DWORD  dwFillAttribute;
    DWORD  dwFlags;
    WORD   wShowWindow;
    WORD   cbReserved2;
    LPBYTE lpReserved2;
    HANDLE hStdInput;
    HANDLE hStdOutput;
    HANDLE hStdError;
} STARTUPINFO, *LPSTARTUPINFO;

typedef struct {
    HANDLE hProcess;
    HANDLE hThread;
    DWORD  dwProcessId;
    DWORD  dwThreadId;
} PROCESS_INFORMATION, *LPPROCESS_INFORMATION;

// Misc. constants
#define _O_BINARY ...
#define _O_TEXT ...


// Constants we need exposed on the compiled lib.  The values for these
// are bound when the library is built.
#define PIPE_NOWAIT ...
#define DUPLICATE_SAME_ACCESS ...
#define STARTF_USESTDHANDLES ...
#define DUPLICATE_SAME_ACCESS ...
#define DUPLICATE_SAME_ACCESS ...
#define CREATE_UNICODE_ENVIRONMENT ...
#define INFINITE ...

// Process access rights
#define PROCESS_QUERY_LIMITED_INFORMATION ...
#define PROCESS_DUP_HANDLE ...
#define PROCESS_TERMINATE ...

// Error codes
#define ERROR_ACCESS_DENIED ...
#define ERROR_INVALID_PARAMETER ...
#define ERROR_FILE_NOT_FOUND ...
#define ERROR_PATH_NOT_FOUND ...
#define ERROR_INVALID_NAME ...
#define ERROR_DIRECTORY ...


// Other functions we're exposing
int open_handle(HANDLE, int);

// Windows API functions we're exposing
BOOL CreatePipe(PHANDLE, PHANDLE, LPSECURITY_ATTRIBUTES, DWORD);
BOOL SetNamedPipeHandleState(HANDLE, LPDWORD, LPDWORD, LPDWORD);
HANDLE GetCurrentProcess();
BOOL DuplicateHandle(HANDLE, HANDLE, HANDLE, LPHANDLE, DWORD, BOOL, DWORD);
BOOL CreateProcess(
    LPCTSTR, LPTSTR, LPSECURITY_ATTRIBUTES, LPSECURITY_ATTRIBUTES, BOOL,
    DWORD, LPVOID, LPCTSTR, LPSTARTUPINFO, LPPROCESS_INFORMATION);
BOOL CloseHandle(HANDLE);
DWORD WaitForSingleObject(HANDLE, DWORD);
HANDLE OpenProcess(DWORD, BOOL, DWORD);
