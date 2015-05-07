# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.win32}.
"""

from twisted.trial import unittest
from twisted.python import win32
from twisted.python.compat import _PY3


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


class TestWindowsLibrariesTest(unittest.TestCase):
    """
    Tests for L{twisted.python.win32._getWindowsLibraries}.
    """
    def test_setsUnicode(self):
        """
        Tests to ensure that the resulting instance of cffi.FFI is
        unicode.  This is required for some of the types we're using
        in the Windows api.
        """
        ffi = win32._getWindowsLibraries()[0]
        self.assertTrue(ffi._windows_unicode)


class RaiseErrorIfZeroTests(unittest.TestCase):
    """
    Tests for L{twisted.python.win32._raiseErrorIfZero}.
    """
    def test_raisesTypeError(self):
        """
        TypeError should be raised if the first argument
        to _raiseErrorIfZero is not an integer.
        """
        with self.assertRaises(TypeError):
            win32._raiseErrorIfZero(1.0, "")

    def test_raisesWindowsAPIError(self):
        """
        Test that win32._raiseErrorIfZero(0, "") raises WindowsAPIError
        """
        with self.assertRaises(win32.WindowsAPIError):
            win32._raiseErrorIfZero(0, "")

    def test_noErrorForPositiveInt(self):
        """
        Test that win32._raiseErrorIfZero(1, "") does nothing.
        """
        win32._raiseErrorIfZero(1, "")

    def test_noErrorForNegativeInt(self):
        """
        Test that win32._raiseErrorIfZero(-1, "") does nothing.

        This test exists to guard against a change that modifies the logic
        of _raiseErrorIfZero from ``if ok == 0:`` to ``if ok >= 0`` or similar
        statement. The type of errors _raiseErrorIfZero handles are
        documented by Microsoft such that any non-zero value is considered
        success.  If this test breaks either _raiseErrorIfZero was updated on
        purpose to allow for a new value or the value being passed into
        _raiseErrorIfZero is incorrect and someone thought they found a bug.
        """
        win32._raiseErrorIfZero(-1, "")

    def test_allowsLongForOk(self):
        """
        In Python 2 int and long are two different things however in Python
        3 there's only int.  This test ensures we accept a long when it's
        available because the Windows API can sometimes return a long even
        though a number can fit within an int.
        """
        if not _PY3:
            win32._raiseErrorIfZero(long(1), "")


class OpenProcessTests(unittest.TestCase):
    """
    Tests for L{twisted.python.win32.OpenProcess}.
    """
    def test_openFailure(self):
        """
        The default arguments to OpenProcess should
        cause an exception to be raised because we don't
        assume what level of access someone will need.
        """
        with self.assertRaises(win32.WindowsAPIError):
            win32.OpenProcess()

    def test_openFailureMessage(self):
        """
        Tests the content of the error message.  Normally this is not
        something we'd test but in this case the exception arguments
        are used elsewhere in the code base.
        """
        try:
            win32.OpenProcess()
        except win32.WindowsAPIError as error:
            self.assertEqual(
                error.args, (
                    win32.kernel32.ERROR_ACCESS_DENIED,
                    "OpenProcess",
                    "Access is denied"
                )
            )


class CloseHandleTests(unittest.TestCase):
    """
    Tests for L{twisted.python.win32.CloseHandle}.
    """
    def test_closesReader(self):
        """
        Creates two pipes, closes the reader and then attempts to
        read from it (which we should not be able to do).
        """
        reader, writer = win32.CreatePipe()
        win32.CloseHandle(reader)
