# -*- test-case-name: twisted.test.test_lockfile -*-
# Copyright (c) 2005 Divmod, Inc.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Filesystem-based interprocess mutex.
"""

from __future__ import absolute_import, division

import errno
import os
from errno import ENOENT, EEXIST
from os.path import dirname

from time import time as _uniquefloat

from twisted.python.compat import _PY3
from twisted.python.deprecate import deprecated, deprecatedModuleAttribute
from twisted.python.runtime import platform
from twisted.python.versions import Version


def unique():
    return str(int(_uniquefloat() * 1000))

if not platform.isWindows():
    from os import symlink
    from os import readlink
    from os import remove as rmlink

    @deprecated(Version("Twisted", 15, 6, 0), replacement="os.kill")
    def kill(pid, signal):
        """
        Passes arguments to L{os.kill} for backwards compatibility.

        @param pid: The process id to pass to L{os.kill}
        @type pid: C{int}

        @param signal: The signal to pass to L{os.kill}
        @type signal: C{int}
        """
        os.kill(pid, signal)

    _windows = False
else:
    from os import rename
    from pywincffi.core import dist
    from pywincffi.exceptions import WindowsAPIError
    from pywincffi.kernel32 import (
        CloseHandle, CreateFile, WriteFile, FlushFileBuffers, pid_exists)

    _windows = True

    # On UNIX, a symlink can be made to a nonexistent location, and
    # FilesystemLock uses this by making the target of the symlink an
    # imaginary, non-existing file named that of the PID of the process with
    # the lock. This has some benefits on UNIX -- making and removing this
    # symlink is atomic. - hawkie
    # On Windows, there's no such thing as a symlink and atomic renames appear
    # to be possible so long as you're using an NTFS file system and not
    # performing the rename across volumes.  Several projects including
    # Python (os.replace in Python 3.3), Go (os.Rename) and cygwin (mv)
    # have implemented this on top of MoveFileEx which a developer from
    # Microsoft claims is atomic (see: "FAQ: Is MoveFileEx atomic"):
    #   https://msdn.microsoft.com/en-us/library/aa365240
    # Other suggested methods of implementing atomic renames include
    # NtSetInformationFile or using transactions however these methods either
    # only support Vista and up or are unsupported and may be removed at a
    # later date.  So long story short, we MoveFileEx to rename the file so
    # we're given the best chance having an atomic rename occur. - opalmer
    #

    ERROR_ACCESS_DENIED = 5
    ERROR_INVALID_PARAMETER = 87

    deprecatedModuleAttribute(
        Version("Twisted", 15, 6, 0),
        "Use of ERROR_ACCESS_DENIED from twisted.python.lockfile "
        "is deprecated",
        "twisted.python.lockfile",
        "ERROR_ACCESS_DENIED"
    )
    deprecatedModuleAttribute(
        Version("Twisted", 15, 6, 0),
        "Use of ERROR_INVALID_PARAMETER from twisted.python.lockfile "
        "is deprecated",
        "twisted.python.lockfile",
        "ERROR_INVALID_PARAMETER"
    )

    @deprecated(Version("Twisted", 15, 6, 0))
    def kill(pid, signal):
        """
        Passes arguments to C{os.kill} and raises OSError(errno.ESRCH, None)
        if Windows responds with ERROR_INVALID_PARAMETER.

        @param pid: The process id to pass to the private function
        @type pid: C{int}

        @param signal: The signal to pass to the private function.
        @type signal: C{int}
        """
        error_access_denied = 5
        error_invalid_parameter = 87
        try:
            os.kill(pid, signal)
        except WindowsError as error:
            if error.winerror == error_access_denied:
                return
            elif error.winerror == error_invalid_parameter:
                raise OSError(errno.ESRCH, None)
            raise

    # For monkeypatching in tests
    _open = open

    @deprecated(Version("Twisted", 15, 6, 0))
    def symlink(value, filename):
        """
        Write a file at C{filename} with the contents of C{value}. See the
        above comment block as to why this is needed.
        """
        # XXX Implement an atomic thingamajig for win32
        newlinkname = filename + "." + unique() + '.newlink'
        newvalname = os.path.join(newlinkname, "symlink")
        os.mkdir(newlinkname)

        # Python 3 does not support the 'commit' flag of fopen in the MSVCRT
        # (http://msdn.microsoft.com/en-us/library/yeby3zcb%28VS.71%29.aspx)
        if _PY3:
            mode = 'w'
        else:
            mode = 'wc'

        with _open(newvalname, mode) as f:
            f.write(value)
            f.flush()

        try:
            rename(newlinkname, filename)
        except:
            os.remove(newvalname)
            os.rmdir(newlinkname)
            raise

    @deprecated(Version("Twisted", 15, 6, 0))
    def readlink(filename):
        """
        Read the contents of C{filename}. See the above comment block as to why
        this is needed.
        """
        filename = os.path.join(filename, "symlink")
        try:
            with open(filename, "r") as file_:
                return file_.read()
        except IOError as e:
            if e.errno == errno.ENOENT or e.errno == errno.EIO:
                raise OSError(e.errno, None)
            raise

    @deprecated(Version("Twisted", 15, 6, 0))
    def rmlink(filename):
        os.remove(os.path.join(filename, 'symlink'))
        os.rmdir(filename)



class FilesystemLock(object):
    """
    A mutex.

    This relies on the filesystem property that creating
    a symlink is an atomic operation and that it will
    fail if the symlink already exists.  Deleting the
    symlink will release the lock.

    @ivar name: The name of the file associated with this lock.

    @ivar clean: Indicates whether this lock was released cleanly by its
        last owner.  Only meaningful after C{lock} has been called and
        returns True.

    @ivar locked: Indicates whether the lock is currently held by this
        object.
    """

    clean = None
    locked = False

    def __init__(self, name):
        self.name = name
        self._hFile = None


    def _lockPosix(self):
        """
        Called by C{lock} when running on POSIX based platforms.
        """
        clean = True
        while True:
            try:
                symlink(str(os.getpid()), self.name)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    try:
                        pid = readlink(self.name)
                    except (IOError, OSError) as e:
                        if e.errno == errno.ENOENT:
                            # The lock has vanished, try to claim it in
                            # the next iteration through the loop.
                            continue
                        raise
                    try:
                        os.kill(int(pid), 0)
                    except OSError as e:
                        if e.errno == errno.ESRCH:
                            # The owner has vanished, try to claim it in
                            # the next iteration through the loop.
                            try:
                                rmlink(self.name)
                            except OSError as e:
                                if e.errno == errno.ENOENT:
                                    # Another process cleaned up the lock.
                                    # Race them to acquire it in the next
                                    # iteration through the loop.
                                    continue
                                raise
                            clean = False
                            continue
                        raise
                    return False
                raise
            self.locked = True
            self.clean = clean
            return True

    def _windowsWriteLockFile(self):
        """
        Called by C{lockWindows} to write a file to disk containing the
        current process id using the CreateFile, WriteFile and
        FlushFileBuffers Windows API calls.  This method will:

            * Create any parent directories for the lock file
            * Create the file using GENERIC_WRITE and FILE_SHARE_READ
              permissions (so other processes cannot write to the file).
            * Write the current pid to the file.
            * Flush the changes to disk.
        """
        try:
            os.makedirs(dirname(self.name))
        except (OSError, IOError, WindowsError) as error:
            if error.errno != EEXIST:
                raise

        _, library = dist.load()
        try:
            self._hFile = CreateFile(
                self.name,
                library.GENERIC_WRITE,

                # Other processes can read from the file but won't
                # be able to move or write to it.
                library.FILE_SHARE_READ
            )
            pid = str(os.getpid())
            if _PY3:
                pid = pid.encode("utf-8")

            WriteFile(self._hFile, pid, lpBufferType="char[]")
            FlushFileBuffers(self._hFile)

        # If one of the Window's APIs raise an exception we need to
        # be sure we discard the handle.
        except WindowsAPIError:
            if self._hFile is not None:
                try:
                    CloseHandle(self._hFile)
                except WindowsAPIError:
                    pass

            self._hFile = None
            raise

    def _lockWindows(self):
        """
        Called by C{lock} on Windows.  This method will:

            * Return the current lock state if this class instance
              created the lock.
            * Write the lock file and return the lock state if the
              lock file does not exist.
            * If the lock file exists, open it and check to see if
              the pid still exists.  If not, write the lock file.
        """
        if self._hFile:  # already locked by this instance
            return self.locked

        try:
            with open(self.name, "r") as file_:
                pid = int(file_.read().rstrip("\x00"))
        except (OSError, IOError, WindowsError) as error:
            if error.errno == ENOENT:
                self._windowsWriteLockFile()
                self.locked = True
                self.clean = True
                return self.locked
            raise
        else:
            if not pid_exists(pid):
                self.clean = False

            self._windowsWriteLockFile()
            self.locked = True
            return self.locked


    def _unlockPosix(self):
        """
        Release the lock on POSIX, called by C{unlock} on POSIX systems.
        """
        pid = readlink(self.name)
        if int(pid) != os.getpid():
            raise ValueError("Lock %r not owned by this process" % self.name)
        rmlink(self.name)
        self.locked = False


    def _unlockWindows(self):
        """
        Release the lock on Windows if we own it, called by C{unlock}.
        """
        # If this class instance has a handle for the file
        if self._hFile:
            CloseHandle(self._hFile)
            os.remove(self.name)
            self._hFile = None
            return

        try:
            with open(self.name, "r") as file_:
                existing_pid = int(file_.read().rstrip("\x00"))
        except (OSError, IOError, WindowsError) as error:
            # Nothing to do if the file does not exist.  It could have
            # been removed in another process or it might have never
            # existed.
            if error.errno == ENOENT:
                return
            raise

        if existing_pid == os.getpid():
            return

        if pid_exists(existing_pid):
            raise ValueError(
                "Lock %r not owned by this process" % self.name)

        os.remove(self.name)
        self.clean = None
        self.locked = None


    def lock(self):
        """
        Acquire this lock.

        @rtype: C{bool}
        @return: True if the lock is acquired, false otherwise.

        @raise: Any exception os.symlink() may raise, other than
        EEXIST.
        """
        if not _windows:
            return self._lockPosix()
        else:
            return self._lockWindows()


    def unlock(self):
        """
        Release this lock.

        @raise: Any exception os.readlink() may raise, or
        ValueError if the lock is not owned by this process.
        """
        if not _windows:
            self._unlockPosix()
        else:
            self._unlockWindows()


def isLocked(name):
    """
    Determine if the lock of the given name is held or not.

    @type name: C{str}
    @param name: The filesystem path to the lock to test

    @rtype: C{bool}
    @return: True if the lock is held, False otherwise.
    """
    l = FilesystemLock(name)
    result = None
    try:
        result = l.lock()
    finally:
        if result:
            l.unlock()
    return not result



__all__ = ['FilesystemLock', 'isLocked']
