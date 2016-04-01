# Copyright (c) 2005 Divmod, Inc.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.lockfile}.
"""

from __future__ import absolute_import, division, print_function

import errno
import json
import os
import sys
from os.path import abspath, dirname, basename
from textwrap import dedent

from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.protocol import ProcessProtocol
from twisted.trial import unittest
from twisted.trial._synctest import SkipTest
from twisted.python import lockfile
from twisted.python.runtime import platform


class PythonProcessProtocol(ProcessProtocol):
    def __init__(self):
        self.started = Deferred()
        self.finished = Deferred()
        self.success = False
        self.locked = False

    def connectionMade(self):
        self.pid = self.transport.pid
        self.started.callback(self.pid)

    def processExited(self, reason):
        self.success = reason.value.exitCode == 0
        self.finished.callback(self.success)

    def outReceived(self, data):
        try:
            self.locked = json.loads(data)["lock"]
        except ValueError:
            pass


class UtilTests(unittest.TestCase):
    """
    Tests for the helper functions used to implement L{FilesystemLock}.
    """
    def test_symlinkEEXIST(self):
        """
        L{lockfile.symlink} raises L{OSError} with C{errno} set to L{EEXIST}
        when an attempt is made to create a symlink which already exists.
        """
        name = self.mktemp()
        lockfile.symlink('foo', name)
        exc = self.assertRaises(OSError, lockfile.symlink, 'foo', name)
        self.assertEqual(exc.errno, errno.EEXIST)


    def test_symlinkEIOWindows(self):
        """
        L{lockfile.symlink} raises L{OSError} with C{errno} set to L{EIO} when
        the underlying L{rename} call fails with L{EIO}.

        Renaming a file on Windows may fail if the target of the rename is in
        the process of being deleted (directory deletion appears not to be
        atomic).
        """
        name = self.mktemp()
        def fakeRename(src, dst):
            raise IOError(errno.EIO, None)
        self.patch(lockfile, 'rename', fakeRename)
        exc = self.assertRaises(IOError, lockfile.symlink, name, "foo")
        self.assertEqual(exc.errno, errno.EIO)
    if not platform.isWindows():
        test_symlinkEIOWindows.skip = (
            "special rename EIO handling only necessary and correct on "
            "Windows.")


    def test_readlinkENOENT(self):
        """
        L{lockfile.readlink} raises L{OSError} with C{errno} set to L{ENOENT}
        when an attempt is made to read a symlink which does not exist.
        """
        name = self.mktemp()
        exc = self.assertRaises(OSError, lockfile.readlink, name)
        self.assertEqual(exc.errno, errno.ENOENT)


    def testkill(self):
        """
        L{lockfile.kill} returns without error if passed the PID of a
        process which exists and signal C{0}.
        """
        lockfile.kill(os.getpid(), 0)


    def testkillERROR_ACCESS_DENIEDWindows(self):
        """
        L{lockfile.kill} returns without error if ERROR_ACCESS_DENIED is
        raised by Windows.
        """
        def fakeKill(pid, signal):
            raise WindowsError(lockfile.ERROR_ACCESS_DENIED, None)

        self.patch(os, 'kill', fakeKill)
        lockfile.kill(0, 0)

    if not platform.isWindows():
        testkillERROR_ACCESS_DENIEDWindows.skip = (
            "special ERROR_ACCESS_DENIED handling in kill() only necessary on "
            "on Windows.")


    def testkillERROR_INVALID_PARAMETERWindows(self):
        """
        L{lockfile.kill} reraises as OSError(ESRCH) if
        ERROR_INVALID_PARAMETER is raised by Windows.
        """
        def fakeKill(pid, signal):
            raise WindowsError(lockfile.ERROR_INVALID_PARAMETER, None)

        self.patch(os, 'kill', fakeKill)

        exc = self.assertRaises(OSError, lockfile.kill, 0, 0)
        self.assertEqual(exc.errno, errno.ESRCH)

    if not platform.isWindows():
        testkillERROR_INVALID_PARAMETERWindows.skip = (
            "special ERROR_INVALID_PARAMETER handling in kill() only "
            "necessary on Windows.")


    def testkillOtherWindowsErrorReraisedOnWindows(self):
        """
        L{lockfile.kill} reraises any unhandled WindowsError on Windows.
        """
        def fakeKill(pid, signal):
            raise WindowsError(123, errno.EINVAL)

        self.patch(os, 'kill', fakeKill)
        exc = self.assertRaises(WindowsError, lockfile.kill, 0, 0)
        self.assertEqual(exc.winerror, 123)
        self.assertEqual(exc.errno, errno.EINVAL)

    if not platform.isWindows():
        testkillOtherWindowsErrorReraisedOnWindows.skip = (
            "special handling in kill() for other WindowsError only necessary "
            "on Windows.")


    def testkillOtherErrorReraisedOnWindows(self):
        """
        L{lockfile.kill} reraises any other unhandled exception on Windows.
        """
        def fakeKill(pid, signal):
            raise IOError(123)

        self.patch(os, 'kill', fakeKill)
        exc = self.assertRaises(IOError, lockfile.kill, 0, 0)
        self.assertEqual(exc.args, (123, ))

    if not platform.isWindows():
        testkillOtherErrorReraisedOnWindows.skip = (
            "special handling in kill() for other WindowsError only necessary "
            "on Windows.")


    def testkillESRCH(self):
        """
        L{lockfile.kill} raises L{OSError} with errno of L{ESRCH} if
        passed a PID which does not correspond to any process.
        """
        # Hopefully there is no process with PID 2 ** 31 - 1
        exc = self.assertRaises(OSError, lockfile.kill, 2 ** 31 - 1, 0)
        self.assertEqual(exc.errno, errno.ESRCH)


    def test_deprecatedKillCallsPrivateFunction(self):
        """
        The deprecated function L{lockfile.kill} should be calling
        the internal private L{twisted.python.lockfile.kill} function.
        """
        def mockedPrivateKill(pid, signal):
            raise ValueError

        self.patch(lockfile, "kill", mockedPrivateKill)
        self.assertRaises(ValueError, lockfile.kill, 0, 0)



class LockingTestsPosix(unittest.TestCase):
    def setUp(self):
        if platform.isWindows():
            raise SkipTest("These lock tests don't run on Windows")

    def _symlinkErrorTest(self, errno):
        def fakeSymlink(source, dest):
            raise OSError(errno, None)
        self.patch(lockfile, 'symlink', fakeSymlink)

        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        exc = self.assertRaises(OSError, lock.lock)
        self.assertEqual(exc.errno, errno)


    def test_symlinkError(self):
        """
        An exception raised by C{symlink} other than C{EEXIST} is passed up to
        the caller of L{FilesystemLock.lock}.
        """
        self._symlinkErrorTest(errno.ENOSYS)


    def test_symlinkErrorPOSIX(self):
        """
        An L{OSError} raised by C{symlink} on a POSIX platform with an errno of
        C{EACCES} or C{EIO} is passed to the caller of L{FilesystemLock.lock}.

        On POSIX, unlike on Windows, these are unexpected errors which cannot
        be handled by L{FilesystemLock}.
        """
        self._symlinkErrorTest(errno.EACCES)
        self._symlinkErrorTest(errno.EIO)

    if platform.isWindows():
        test_symlinkErrorPOSIX.skip = (
            "POSIX-specific error propagation not expected on Windows.")


    def test_cleanlyAcquire(self):
        """
        If the lock has never been held, it can be acquired and the C{clean}
        and C{locked} attributes are set to C{True}.
        """
        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        self.assertTrue(lock.lock())
        self.assertTrue(lock.clean)
        self.assertTrue(lock.locked)


    def test_cleanlyRelease(self):
        """
        If a lock is released cleanly, it can be re-acquired and the C{clean}
        and C{locked} attributes are set to C{True}.
        """
        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        self.assertTrue(lock.lock())
        lock.unlock()
        self.assertFalse(lock.locked)

        lock = lockfile.FilesystemLock(lockf)
        self.assertTrue(lock.lock())
        self.assertTrue(lock.clean)
        self.assertTrue(lock.locked)


    def test_cannotLockLocked(self):
        """
        If a lock is currently locked, it cannot be locked again.
        """
        lockf = self.mktemp()
        firstLock = lockfile.FilesystemLock(lockf)
        self.assertTrue(firstLock.lock())

        secondLock = lockfile.FilesystemLock(lockf)
        self.assertFalse(secondLock.lock())
        self.assertFalse(secondLock.locked)


    def test_uncleanlyAcquire(self):
        """
        If a lock was held by a process which no longer exists, it can be
        acquired, the C{clean} attribute is set to C{False}, and the
        C{locked} attribute is set to C{True}.
        """
        owner = 12345

        def fakeKill(pid, signal):
            if signal != 0:
                raise OSError(errno.EPERM, None)
            if pid == owner:
                raise OSError(errno.ESRCH, None)

        lockf = self.mktemp()
        self.patch(lockfile, 'kill', fakeKill)
        lockfile.symlink(str(owner), lockf)

        lock = lockfile.FilesystemLock(lockf)
        self.assertTrue(lock.lock())
        self.assertFalse(lock.clean)
        self.assertTrue(lock.locked)

        self.assertEqual(lockfile.readlink(lockf), str(os.getpid()))


    def test_lockReleasedBeforeCheck(self):
        """
        If the lock is initially held but then released before it can be
        examined to determine if the process which held it still exists, it is
        acquired and the C{clean} and C{locked} attributes are set to C{True}.
        """
        def fakeReadlink(name):
            # Pretend to be another process releasing the lock.
            lockfile.rmlink(lockf)
            # Fall back to the real implementation of readlink.
            readlinkPatch.restore()
            return lockfile.readlink(name)
        readlinkPatch = self.patch(lockfile, 'readlink', fakeReadlink)

        def fakeKill(pid, signal):
            if signal != 0:
                raise OSError(errno.EPERM, None)
            if pid == 43125:
                raise OSError(errno.ESRCH, None)
        self.patch(lockfile, 'kill', fakeKill)

        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        lockfile.symlink(str(43125), lockf)
        self.assertTrue(lock.lock())
        self.assertTrue(lock.clean)
        self.assertTrue(lock.locked)


    def test_lockReleasedDuringAcquireSymlink(self):
        """
        If the lock is released while an attempt is made to acquire
        it, the lock attempt fails and C{FilesystemLock.lock} returns
        C{False}.  This can happen on Windows when L{lockfile.symlink}
        fails with L{IOError} of C{EIO} because another process is in
        the middle of a call to L{os.rmdir} (implemented in terms of
        RemoveDirectory) which is not atomic.
        """
        def fakeSymlink(src, dst):
            # While another process id doing os.rmdir which the Windows
            # implementation of rmlink does, a rename call will fail with EIO.
            raise OSError(errno.EIO, None)

        self.patch(lockfile, 'symlink', fakeSymlink)

        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        self.assertFalse(lock.lock())
        self.assertFalse(lock.locked)
    if not platform.isWindows():
        test_lockReleasedDuringAcquireSymlink.skip = (
            "special rename EIO handling only necessary and correct on "
            "Windows.")


    def test_lockReleasedDuringAcquireReadlink(self):
        """
        If the lock is initially held but is released while an attempt
        is made to acquire it, the lock attempt fails and
        L{FilesystemLock.lock} returns C{False}.
        """
        def fakeReadlink(name):
            # While another process is doing os.rmdir which the
            # Windows implementation of rmlink does, a readlink call
            # will fail with EACCES.
            raise IOError(errno.EACCES, None)
        self.patch(lockfile, 'readlink', fakeReadlink)

        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        lockfile.symlink(str(43125), lockf)
        self.assertFalse(lock.lock())
        self.assertFalse(lock.locked)
    if not platform.isWindows():
        test_lockReleasedDuringAcquireReadlink.skip = (
            "special readlink EACCES handling only necessary and correct on "
            "Windows.")


    def _readlinkErrorTest(self, exceptionType, errno):
        def fakeReadlink(name):
            raise exceptionType(errno, None)
        self.patch(lockfile, 'readlink', fakeReadlink)

        lockf = self.mktemp()

        # Make it appear locked so it has to use readlink
        lockfile.symlink(str(43125), lockf)

        lock = lockfile.FilesystemLock(lockf)
        exc = self.assertRaises(exceptionType, lock.lock)
        self.assertEqual(exc.errno, errno)
        self.assertFalse(lock.locked)


    def test_readlinkError(self):
        """
        An exception raised by C{readlink} other than C{ENOENT} is passed up to
        the caller of L{FilesystemLock.lock}.
        """
        self._readlinkErrorTest(OSError, errno.ENOSYS)
        self._readlinkErrorTest(IOError, errno.ENOSYS)


    def test_readlinkErrorPOSIX(self):
        """
        Any L{IOError} raised by C{readlink} on a POSIX platform passed to the
        caller of L{FilesystemLock.lock}.

        On POSIX, unlike on Windows, these are unexpected errors which cannot
        be handled by L{FilesystemLock}.
        """
        self._readlinkErrorTest(IOError, errno.ENOSYS)
        self._readlinkErrorTest(IOError, errno.EACCES)
    if platform.isWindows():
        test_readlinkErrorPOSIX.skip = (
            "POSIX-specific error propagation not expected on Windows.")


    def test_lockCleanedUpConcurrently(self):
        """
        If a second process cleans up the lock after a first one checks the
        lock and finds that no process is holding it, the first process does
        not fail when it tries to clean up the lock.
        """
        def fakeRmlink(name):
            rmlinkPatch.restore()
            # Pretend to be another process cleaning up the lock.
            lockfile.rmlink(lockf)
            # Fall back to the real implementation of rmlink.
            return lockfile.rmlink(name)
        rmlinkPatch = self.patch(lockfile, 'rmlink', fakeRmlink)

        def fakeKill(pid, signal):
            if signal != 0:
                raise OSError(errno.EPERM, None)
            if pid == 43125:
                raise OSError(errno.ESRCH, None)
        self.patch(lockfile, 'kill', fakeKill)

        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        lockfile.symlink(str(43125), lockf)
        self.assertTrue(lock.lock())
        self.assertTrue(lock.clean)
        self.assertTrue(lock.locked)


    def test_rmlinkError(self):
        """
        An exception raised by L{rmlink} other than C{ENOENT} is passed up
        to the caller of L{FilesystemLock.lock}.
        """
        def fakeRmlink(name):
            raise OSError(errno.ENOSYS, None)
        self.patch(lockfile, 'rmlink', fakeRmlink)

        def fakeKill(pid, signal):
            if signal != 0:
                raise OSError(errno.EPERM, None)
            if pid == 43125:
                raise OSError(errno.ESRCH, None)
        self.patch(lockfile, 'kill', fakeKill)

        lockf = self.mktemp()

        # Make it appear locked so it has to use readlink
        lockfile.symlink(str(43125), lockf)

        lock = lockfile.FilesystemLock(lockf)
        exc = self.assertRaises(OSError, lock.lock)
        self.assertEqual(exc.errno, errno.ENOSYS)
        self.assertFalse(lock.locked)


    def testkillError(self):
        """
        If L{kill} raises an exception other than L{OSError} with errno set to
        C{ESRCH}, the exception is passed up to the caller of
        L{FilesystemLock.lock}.
        """
        def fakeKill(pid, signal):
            raise OSError(errno.EPERM, None)
        self.patch(lockfile, 'kill', fakeKill)

        lockf = self.mktemp()

        # Make it appear locked so it has to use readlink
        lockfile.symlink(str(43125), lockf)

        lock = lockfile.FilesystemLock(lockf)
        exc = self.assertRaises(OSError, lock.lock)
        self.assertEqual(exc.errno, errno.EPERM)
        self.assertFalse(lock.locked)


    def test_unlockOther(self):
        """
        L{FilesystemLock.unlock} raises L{ValueError} if called for a lock
        which is held by a different process.
        """
        lockf = self.mktemp()
        lockfile.symlink(str(os.getpid() + 1), lockf)
        lock = lockfile.FilesystemLock(lockf)
        self.assertRaises(ValueError, lock.unlock)


    def test_isLocked(self):
        """
        L{isLocked} returns C{True} if the named lock is currently locked,
        C{False} otherwise.
        """
        lockf = self.mktemp()
        self.assertFalse(lockfile.isLocked(lockf))
        lock = lockfile.FilesystemLock(lockf)
        self.assertTrue(lock.lock())
        self.assertTrue(lockfile.isLocked(lockf))
        lock.unlock()
        self.assertFalse(lockfile.isLocked(lockf))


class FunctionalLockTests(unittest.TestCase):
    """
    These tests are designed to ensure that the behavior of FilesystemLock
    is consistent across platforms and with prior versions of the class.
    """
    def _writePythonScripts(self, lockPath=None):
        if lockPath is None:
            lockPath = abspath(self.mktemp())

        script = dedent("""
        from __future__ import print_function
        import sys
        import json

        sys.path.insert(0, %r)
        from twisted.python.lockfile import FilesystemLock

        lock = FilesystemLock(%r)
        print(json.dumps({"lock": lock.lock()}))
         """) % (
            dirname(dirname(
                dirname(abspath(lockfile.__file__)))).replace("\\", "/"),
            abspath(lockPath).replace("\\", "/")
        )

        scriptPath = self.mktemp()
        with open(scriptPath, "w") as file_:
            file_.write(script)

        return scriptPath, lockPath

    def testLock(self):
        """
        Process 1 calls FilesystemLock(file).lock(), returning True.
        """
        lock = lockfile.FilesystemLock(self.mktemp())
        self.assertTrue(lock.lock())
        self.assertFalse(lock.lock())

    def testLockCalledMultipleTimesBySameProcess(self):
        """
        Only the first call to FilesystemLock(file).lock() will return True,
        even if the calling process owns the lock.
        """
        lock = lockfile.FilesystemLock(self.mktemp())
        lock.lock()
        self.assertFalse(lock.lock())

    @inlineCallbacks
    def testLockCalledByExternalProcess(self):
        """
        Only the first process to call FilesystemLock(file).lock() should
        be able to acquire the lock.
        """
        lockPath = abspath(self.mktemp())
        lock = lockfile.FilesystemLock(lockPath)
        self.assertTrue(lock.lock())

        scriptPath, _ = self._writePythonScripts(lockPath=lockPath)

        protocol = PythonProcessProtocol()
        reactor.spawnProcess(
            protocol, sys.executable, [basename(sys.executable), scriptPath]
        )

        yield protocol.started
        yield protocol.finished
        self.assertEqual(
            protocol.success, True,
            "Subprocess has failed for an unknown reason")

        self.assertFalse(protocol.locked)

    @inlineCallbacks
    def testAcquiresStaleLock(self):
        """
        A process launches and calls Only the first process to calls
        FilesystemLock(file).lock() but dies and leaves the lock file
        behind.  Another process should be able to acquire the lock again.
        """
        # First process acquires lock
        scriptPath, lockPath = self._writePythonScripts()
        protocol = PythonProcessProtocol()
        reactor.spawnProcess(
            protocol, sys.executable, [basename(sys.executable), scriptPath]
        )

        yield protocol.started
        yield protocol.finished
        self.assertEqual(
            protocol.success, True,
            "Subprocess has failed for an unknown reason")

        self.assertTrue(protocol.locked)

        # Second process acquires lock
        protocol = PythonProcessProtocol()
        reactor.spawnProcess(
            protocol, sys.executable, [basename(sys.executable), scriptPath]
        )

        yield protocol.started
        yield protocol.finished
        self.assertEqual(
            protocol.success, True,
            "Subprocess has failed for an unknown reason")

        self.assertTrue(protocol.locked)

    # TODO: manually test current release of Twisted fo behavior on Windows and Linux
