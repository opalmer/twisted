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

import re
import os

try:
    import win32api
    import win32con
except ImportError:
    pass

import cffi

from twisted.python.runtime import platform
from twisted.python.util import sibpath


class FakeWindowsError(OSError):
    """
    Stand-in for sometimes-builtin exception on platforms for which it
    is missing.
    """

try:
    WindowsError = WindowsError
except NameError:
    WindowsError = FakeWindowsError


class WindowsAPIError(WindowsError):
    """
    An error which is raised when a Windows API call has
    failed. This exception class is a replacement for
    L{pywintypes.error}.
    """


def _buildLibraryFromSource(
        header=None, source=None, libraries=None, tmpdir=False):
    """
    This function takes a C header and source code and produces an
    instance of L{FFI} as well as the built library. If ``source`` and
    ``header`` are not provided then the default behavior is to load
    win32.h and win32.c from the same directory that this file is in.

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
    if header is None:
        with open(sibpath(__file__, "win32.h"), "rb") as header:
            header = header.read()

    if source is None:
        with open(sibpath(__file__, "win32.c"), "rb") as source:
            source = source.read()

    ffi = cffi.FFI()
    ffi.set_unicode(True)
    ffi.cdef(header)
    return ffi, ffi.verify(source, libraries=libraries, tmpdir=tmpdir)

if os.name == "nt":
    _ffi, winapi = _buildLibraryFromSource(libraries=["kernel32"])

    # TODO: deprecate module level attributes?
    ERROR_FILE_NOT_FOUND = winapi.ERROR_FILE_NOT_FOUND
    ERROR_PATH_NOT_FOUND = winapi.ERROR_PATH_NOT_FOUND
    ERROR_INVALID_NAME = winapi.ERROR_INVALID_NAME
    ERROR_DIRECTORY = winapi.ERROR_DIRECTORY
    O_BINARY = winapi._O_BINARY
else:
    _ffi = None
    winapi = None


def OpenProcess(dwDesiredAccess=0, bInheritHandle=False, dwProcessId=None):
    """
    This function wraps the CFFI implementation of Microsoft's OpenProcess()
    function:

        https://msdn.microsoft.com/en-us/library/windows/desktop/ms684320(v=vs.85).aspx

    @param dwDesiredAccess: The desired access right(s) to the process
    @type dwDesiredAccess: C{int}

    @param bInheritHandle: Should child processes inherit the handle of this process
    @typpe bInheritHandle: C{bool}
    """
    if dwProcessId is None:
        dwProcessId = os.getpid()

    winapi.OpenProcess(dwDesiredAccess, bInheritHandle, dwProcessId)
    code, error = _ffi.getwinerror()
    if code != 0:
        raise WindowsAPIError(code, "OpenProcess", error)


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
        if _ffi is not None:
            FormatMessage = \
                lambda code=-1: _ffi.getwinerror(code=code)[1] + ".\r\n"

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
