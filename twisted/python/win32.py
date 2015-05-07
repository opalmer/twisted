# -*- test-case-name: twisted.python.test.test_win32 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Win32 utilities.

See also twisted.python.shortcut.

@var O_BINARY: the 'binary' mode flag on Windows, or 0 on other platforms, so it
    may safely be OR'ed into a mask for os.open.
"""

from __future__ import division, absolute_import

import os
import re
import tempfile

try:
    import win32api
    import win32con
except ImportError:
    pass

try:
    long_ = long
except NameError:  # Python 3
    long_ = int

import cffi

from twisted.python.runtime import platform
from twisted.python.util import sibpath
from twisted.python.compat import _PY3


class FakeWindowsError(OSError):
    """
    Stand-in for sometimes-builtin exception on platforms for which it
    is missing.
    """

try:
    WindowsError = WindowsError
except NameError:
    WindowsError = FakeWindowsError


class WindowsAPIError(Exception):
    """
    An error which is raised when a Windows API call has
    failed.
    """
    def __init__(self, code, function, error):
        super(WindowsAPIError, self).__init__(code, function, error)
        self.code = code
        self.function = function
        self.error = error


def _getWindowsLibraries():
    """
    This function will return a tuple containing

    @param header: The C header declarations.
    @type header: C{str}

    @param source: The source code of the library to compile.
    @type source: C{str}

    @param libraries: Additional libraries to include while compiling
    @type libraries: C{list}

    @param tmpdir: The directory to provide to L{FFI.verify} which is where
                    cffi should cache the compiled results.  Setting this value
                    to None will result in a TypeError being raised from
                    cffi.
    @type tmpdir: C{str}
    """
    kernel32_ffi = cffi.FFI()
    kernel32_ffi.set_unicode(True)

    with open(sibpath(__file__, "win32_kernel.h"), "rb") as header:
        kernel32_ffi.cdef(header.read())

    kernel32 = kernel32_ffi.dlopen("kernel32")

    return kernel32_ffi, kernel32

O_BINARY = getattr(os, "O_BINARY", None)

if os.name == "nt":
    ffi, kernel32 = _getWindowsLibraries()

    # TODO: deprecate module level attributes?
    ERROR_FILE_NOT_FOUND = kernel32.ERROR_FILE_NOT_FOUND
    ERROR_PATH_NOT_FOUND = kernel32.ERROR_PATH_NOT_FOUND
    ERROR_INVALID_NAME = kernel32.ERROR_INVALID_NAME
    ERROR_DIRECTORY = kernel32.ERROR_DIRECTORY

    # We can't define these in the header so they're defined
    # here.
    FILE_GENERIC_READ = (
        kernel32.STANDARD_RIGHTS_READ |
        kernel32.FILE_READ_DATA |
        kernel32.FILE_READ_ATTRIBUTES |
        kernel32.FILE_READ_EA |
        kernel32.SYNCHRONIZE
    )
    FILE_GENERIC_WRITE = (
        kernel32.STANDARD_RIGHTS_WRITE |
        kernel32.FILE_WRITE_DATA |
        kernel32.FILE_WRITE_ATTRIBUTES |
        kernel32.FILE_WRITE_EA |
        kernel32.FILE_APPEND_DATA |
        kernel32.SYNCHRONIZE
    )
    FILE_GENERIC_EXECUTE = (
        kernel32.STANDARD_RIGHTS_EXECUTE |
        kernel32.FILE_READ_ATTRIBUTES |
        kernel32.FILE_EXECUTE |
        kernel32.SYNCHRONIZE
    )


def _raiseErrorIfZero(ok, function):
    """
    Checks to see if there was an error while calling
    a Windows API function.  This function should only
    be used on Windows API calls which have a return
    value of non-zero for success and zero for failure.

    @param ok: The return value from a Windows API function.
    @type ok: C{int,long}

    @param function: The name of the function that was called
    @type function: C{str}

    @raises WindowsAPIError: Raised if ok != 0
    @raises TypeError: Raised if `ok` is not an integer
    """
    # Be sure we're getting an integer here.  Because we're working
    # with cffi it's possible we could get an object that acts like
    # an integer without in fact being in integer to `ok`.
    if not isinstance(ok, (int, long_)):
        raise TypeError("Internal error, expected integer for `ok`")

    if ok == 0:
        code, error = ffi.getwinerror()
        raise WindowsAPIError(code, function, error)


def OpenProcess(dwDesiredAccess=0, bInheritHandle=False, dwProcessId=None):
    """
    This function wraps Microsoft's OpenProcess() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/ms684320(v=vs.85).aspx

    @param dwDesiredAccess: The desired access right(s) to the process
    @type dwDesiredAccess: C{int}

    @param bInheritHandle: Should child processes inherit the handle of this process
    @type bInheritHandle: C{bool}
    """
    if dwProcessId is None:
        dwProcessId = os.getpid()

    kernel32.OpenProcess(dwDesiredAccess, bInheritHandle, dwProcessId)
    code, error = ffi.getwinerror()
    if code != 0:
        raise WindowsAPIError(code, "OpenProcess", error)


def CreatePipe(inheritHandle=True):
    """
    This function wraps Microsoft's CreatePipe() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa365779(v=vs.85).aspx

    @param inheritHandle: When True the handles returned will be inherited
                          by any new child process.
    @type inheritHandle: C{bool}

    @return: Returns a tuple containing a reader PHANDLE and a writer PHANDLE
    @rtype: C{tuple}
    """
    reader = ffi.new("PHANDLE")
    writer = ffi.new("PHANDLE")
    securityAttributes = ffi.new(
        "SECURITY_ATTRIBUTES[1]", [{
            "nLength": ffi.sizeof("SECURITY_ATTRIBUTES"),
            "bInheritHandle": inheritHandle,
            "lpSecurityDescriptor": ffi.NULL
        }]
    )
    ok = kernel32.CreatePipe(reader, writer, securityAttributes, 0)
    _raiseErrorIfZero(ok, "CreatePipe")

    return reader[0], writer[0]


def ReadFile(handle, readBytes):
    """
    This function wraps Microsoft's ReadFile() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa365467(v=vs.85).aspx

    @param handle: The handle of file or I/O device to read from.

    @param readBytes: The number of bytes to read from ``handle``
    @type readBytes: C{int}
    """
    output = ffi.new("LPVOID[%d]" % readBytes)
    ok = kernel32.ReadFile(handle, output, readBytes, ffi.NULL, ffi.NULL)
    _raiseErrorIfZero(ok, "ReadFile")
    return output


# TODO: parameter type formatting
def WriteFile(handle, data, overlapped=False):
    """
    This function wraps Microsoft's WriteFile() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa365747(v=vs.85).aspx

    @param handle: The handle object to write data to

    @param data: The data to write to the pipe
    @type data: C{str,unicode}

    @param overlapped: Enable or disable overlapping writes.  This value may
                       be a boolean any other value that WriteFile() would
                       normally accept.
    """
    if not _PY3 and not isinstance(data, unicode):
        data = unicode(data)

    size = len(data)
    data = ffi.new("wchar_t[%d]" % size, data)

    if not overlapped:
        overlapped = ffi.NULL

    bytesWritten = ffi.new("LPDWORD")
    ok = kernel32.WriteFile(handle, data, size, bytesWritten, overlapped)
    code, error = ffi.getwinerror()

    # TODO: remove once we know the type of ok (could be TRUE or ok)
    print "(DEBUG) =============", ok

    if ok != 0 or code == kernel32.ERROR_IO_PENDING:
        return bytesWritten

    raise WindowsAPIError(code, "WriteFile", error)


# TODO: finish documentation
# TODO: handle wide vs. ansi function availability
def CreateFile(handle, desiredAccess):
    """
    This function wraps Microsoft's CreateFile() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa363858(v=vs.85).aspx
    """
    kernel32.CreateFileW(handle, )


# TODO: parameter documentation
def SetNamedPipeHandleState(handle, mode):
    """
    This function wraps Microsoft's SetNamedPipeHandleState function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa365787(v=vs.85).aspx
    """
    ok = kernel32.SetNamedPipeHandleState(handle, mode, ffi.NULL, ffi.NULL)
    _raiseErrorIfZero(ok, "SetNamedPipeHandleState")


def PeekNamedPipe(pipe, bufferSize):
    """
    This function wraps Microsoft's PeekNamedPipe() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa365779(v=vs.85).aspx

    @param pipe: The handle of the named pipe to peek into.  This value can
                 be generated using the output from the L{CreatePipe} call.

    @param bufferSize: The size of the buffer to pass into the nBufferSize
                       input to the underlying function.
    @type bufferSize: C{int}
    """
    lpBuffer = ffi.new("LPVOID[%d]" % bufferSize)
    lpBytesLeftThisMessage = ffi.new("LPDWORD")

    ok = kernel32.PeekNamedPipe(
        pipe, lpBuffer, bufferSize, ffi.NULL, ffi.NULL, lpBytesLeftThisMessage
    )
    _raiseErrorIfZero(ok, "PeekNamedPipe")

    return ok, lpBytesLeftThisMessage[0]


def GetTempFileName(unique=True, filenamePrefix=tempfile.template):
    """
    This function wraps Microsoft's GetTempFileName() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa364991(v=vs.85).aspx

    @param unique: If True then Windows will keep generating file names until
                   it's able to produce a unique path.
    @param unique: C{bool}

    @param filenamePrefix: The string to prefix the generated file name
                           with.  If a value is not provided we use
                           L{tempfile.template}
    @type filenamePrefix: C{str,unicode}
    """
    # Get the temporary path
    tempPath = ffi.new("wchar_t[%d]" % kernel32.MAX_PATH)
    ok = kernel32.GetTempPathW(kernel32.MAX_PATH, tempPath)
    _raiseErrorIfZero(ok, "GetTempPathW")

    if not _PY3 and not isinstance(filenamePrefix, unicode):
        filenamePrefix = unicode(filenamePrefix)

    # Generate the file path
    output = ffi.new("wchar_t[%d]" % kernel32.MAX_PATH)
    prefix = ffi.new("wchar_t[%d]" % len(filenamePrefix), filenamePrefix)
    ok = kernel32.GetTempFileNameW(tempPath, prefix, unique, output)
    _raiseErrorIfZero(ok, "GetTempFileNameW")

    return output


def CloseHandle(handle):
    """
    This function wraps Microsoft's CloseHandle() function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/ms724211(v=vs.85).aspx

    @param handle: The handle to close
    """
    ok = kernel32.CloseHandle(handle)
    _raiseErrorIfZero(ok, "CloseHandle")


def getProgramsMenuPath():
    """
    Get the path to the Programs menu.

    Probably will break on non-US Windows.

    @return: the filesystem location of the common Start Menu->Programs.
    @rtype: L{str}
    """
    if not platform.isWindows():
        return "C:\\Windows\\Start Menu\\Programs"
    keyname = 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders'
    hShellFolders = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE,
                                          keyname, 0, win32con.KEY_READ)
    return win32api.RegQueryValueEx(hShellFolders, 'Common Programs')[0]


def getProgramFilesPath():
    """Get the path to the Program Files folder."""
    keyname = 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
    currentV = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE,
                                     keyname, 0, win32con.KEY_READ)
    return win32api.RegQueryValueEx(currentV, 'ProgramFilesDir')[0]


_cmdLineQuoteRe = re.compile(r'(\\*)"')
_cmdLineQuoteRe2 = re.compile(r'(\\+)\Z')
def cmdLineQuote(s):
    """
    Internal method for quoting a single command-line argument.

    @param s: an unquoted string that you want to quote so that something that
        does cmd.exe-style unquoting will interpret it as a single argument,
        even if it contains spaces.
    @type s: C{str}

    @return: a quoted string.
    @rtype: C{str}
    """
    quote = ((" " in s) or ("\t" in s) or ('"' in s) or s == '') and '"' or ''
    return quote + _cmdLineQuoteRe2.sub(r"\1\1", _cmdLineQuoteRe.sub(r'\1\1\\"', s)) + quote

def quoteArguments(arguments):
    """
    Quote an iterable of command-line arguments for passing to CreateProcess or
    a similar API.  This allows the list passed to C{reactor.spawnProcess} to
    match the child process's C{sys.argv} properly.

    @param arglist: an iterable of C{str}, each unquoted.

    @return: a single string, with the given sequence quoted as necessary.
    """
    return ' '.join([cmdLineQuote(a) for a in arguments])


class _ErrorFormatter(object):
    """
    Formatter for Windows error messages.

    @ivar winError: A callable which takes one integer error number argument
        and returns an L{exceptions.WindowsError} instance for that error (like
        L{ctypes.WinError}).

    @ivar formatMessage: A callable which takes one integer error number
        argument and returns a C{str} giving the message for that error (like
        L{win32api.FormatMessage}).

    @ivar errorTab: A mapping from integer error numbers to C{str} messages
        which correspond to those erorrs (like L{socket.errorTab}).
    """
    def __init__(self, WinError, FormatMessage, errorTab):
        self.winError = WinError
        self.formatMessage = FormatMessage
        self.errorTab = errorTab

    def fromEnvironment(cls):
        """
        Get as many of the platform-specific error translation objects as
        possible and return an instance of C{cls} created with them.
        """
        try:
            from ctypes import WinError
        except ImportError:
            WinError = None

        FormatMessage = None
        if ffi is not None:
            FormatMessage = \
                lambda code=-1: ffi.getwinerror(code=code)[1] + ".\r\n"

        try:
            from socket import errorTab
        except ImportError:
            errorTab = None
        return cls(WinError, FormatMessage, errorTab)
    fromEnvironment = classmethod(fromEnvironment)


    def formatError(self, errorcode):
        """
        Returns the string associated with a Windows error message, such as the
        ones found in socket.error.

        Attempts direct lookup against the win32 API via ctypes and then
        pywin32 if available), then in the error table in the socket module,
        then finally defaulting to C{os.strerror}.

        @param errorcode: the Windows error code
        @type errorcode: C{int}

        @return: The error message string
        @rtype: C{str}
        """
        if self.winError is not None:
            return self.winError(errorcode).strerror
        if self.formatMessage is not None:
            return self.formatMessage(errorcode)
        if self.errorTab is not None:
            result = self.errorTab.get(errorcode)
            if result is not None:
                return result
        return os.strerror(errorcode)

formatError = _ErrorFormatter.fromEnvironment().formatError
