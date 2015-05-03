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
from functools import wraps

from cffi import FFI

from twisted.python.runtime import platform
from twisted.python.compat import winreg
from twisted.python.util import sibpath

API_HEADER = sibpath(__file__, "win32.h")
API_SOURCE = sibpath(__file__, "win32.c")

# http://msdn.microsoft.com/library/default.asp?url=/library/en-us/debug/base/system_error_codes.asp
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_INVALID_NAME = 123
ERROR_DIRECTORY = 267

O_BINARY = getattr(os, "O_BINARY", 0)

class FakeWindowsError(OSError):
    """
    Stand-in for sometimes-builtin exception on platforms for which it
    is missing.
    """

try:
    WindowsError = WindowsError
except NameError:
    WindowsError = FakeWindowsError


def getProgramsMenuPath():
    """
    Get the path to the Programs menu.

    Probably will break on non-US Windows.

    @return: the filesystem location of the common Start Menu->Programs.
    @rtype: L{str}
    """
    if not platform.isWindows():
        return "C:\\Windows\\Start Menu\\Programs"

    shell_folders = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders",
        0, winreg.KEY_READ
    )
    try:
        value, _ = winreg.QueryValueEx(shell_folders, "Common Programs")
        return value
    finally:
        shell_folders.Close()


def getProgramFilesPath():
    """Get the path to the Program Files folder."""
    current_value = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        "SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
        0, winreg.KEY_READ
    )
    try:
        value, _ = winreg.QueryValueEx(current_value, "ProgramFilesDir")
        return value
    finally:
        current_value.Close()


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
        try:
            from win32api import FormatMessage
        except ImportError:
            FormatMessage = None
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


def requires_windows(func):
    """
    A decorator which raises NotImplementedError on non-windows
    platforms.  Use this to decorate functions which should only
    be executed on Windows.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if os.name != "nt":
            raise NotImplementedError(
                "win32.%s() is only implemented on Windows" % func.func_name)

        return func(*args, **kwargs)
    return wrapper


@requires_windows
def get_library(header, source):
    """
    This function sets up an instance of L{ffi.api.FFI} and complies
    the header and source files.
    """
    ffi = FFI()
    ffi.set_unicode(True)

    # NOTE: You must load the cdef before calling verify() below.
    with open(source, "rb") as source:
        ffi.cdef(source.read())

    with open(header, "rb") as header:
        lib = ffi.verify(header.read(), libraries=["kernel32"])

    return ffi, lib


try:
    _ffi, _lib = get_library(API_HEADER, API_SOURCE)
except NotImplementedError:
    _ffi = NotImplemented
    _lib = NotImplemented
