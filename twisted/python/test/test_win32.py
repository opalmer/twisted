# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.win32}.
"""

import tempfile

import cffi.verifier

from twisted.trial import unittest
from twisted.python import win32


class CommandLineQuotingTests(unittest.TestCase):
    """
    Tests for L{cmdLineQuote}.
    """

    def test_argWithoutSpaces(self):
        """
        Calling C{cmdLineQuote} with an argument with no spaces should
        return the argument unchanged.
        """
        self.assertEqual(win32.cmdLineQuote('an_argument'), 'an_argument')


    def test_argWithSpaces(self):
        """
        Calling C{cmdLineQuote} with an argument containing spaces should
        return the argument surrounded by quotes.
        """
        self.assertEqual(win32.cmdLineQuote('An Argument'), '"An Argument"')


    def test_emptyStringArg(self):
        """
        Calling C{cmdLineQuote} with an empty string should return a
        quoted empty string.
        """
        self.assertEqual(win32.cmdLineQuote(''), '""')


class GetLibraryFromSourceTests(unittest.TestCase):
    """
    Tests for L{twisted.python.win32.buildLibraryFromSource}.  We will make
    an attempt to cleanup the directory cffi creates but we can't remove
    the directory itself because of the pyd file that gets loaded into
    memory.
    """
    def test_setsUnicode(self):
        """
        Tests to ensure that the resulting instance of cffi.FFI is
        unicode.  This is required for some of the types we're using
        in the Windows api.
        """
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(cffi.verifier.cleanup_tmpdir, tmpdir=tmpdir)
        ffi, lib = win32._getWindowsLibraries(
            "", "", libraries=["kernel32"], tmpdir=tmpdir)
        self.assertTrue(ffi._windows_unicode)

    def test_buildsFunction(self):
        """
        Tests to ensure that the library is complied properly and produces
        a function that we're able to use.  We do this not only to ensure
        our invocation of cffi works but also to ensure that the calls to
        FFI.cdef and FFI.verify are made in the proper order.
        """
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(cffi.verifier.cleanup_tmpdir, tmpdir=tmpdir)
        header = "int addTwo(int value);"
        source = "int addTwo(int value) { return value + 2; }"
        ffi, lib = win32._getWindowsLibraries(
            header, source, libraries=["kernel32"], tmpdir=tmpdir)
        self.assertEqual(lib.addTwo(2), 4)

