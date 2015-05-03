# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.win32}.
"""
import os
from functools import partial

from cffi import FFI

from twisted.trial import unittest
from twisted.python.compat import winreg
from twisted.python.runtime import platform
from twisted.python import win32
from twisted.python.util import sibpath


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


class RequiresWindowsDecoratorTests(unittest.TestCase):
    """
    L{requires_windows} should raise NotImplementedError on
    platforms other than nt.
    """
    def test_decorator_not_nt(self):
        self.patch(os, "name", "foobar")

        @win32.requires_windows
        def function(resultA, resultB=None):
            return

        with self.assertRaisesRegexp(
                NotImplementedError,
                "win32.function\(\) is only implemented on Windows"):
            function()

    def test_decorator_nt(self):
        """
        L{requires_windows} should not interfere with function
        arguments and return values
        """
        self.patch(os, "name", "nt")

        @win32.requires_windows
        def function(resultA, resultB=None):
            return resultA, resultB

        self.assertEqual(function(1, resultB=2), (1, 2))

    def test_doc_string(self):
        """
        Documentation strings are important, wrapping a function
        with L{requires_windows} should not override the doc string.
        """
        @win32.requires_windows
        def function():
            """Test doc string"""

        self.assertEqual("Test doc string", function.__doc__)


class GlobalsTests(unittest.TestCase):
    """
    Tests for globals in L{twisted.python.winapi}.
    """
    def test_header_is_file(self):
        with open(win32.API_HEADER, "rb") as header:
            with open(sibpath(win32.__file__, "win32.h"), "rb") as sib_head:
                self.assertEqual(header.read(), sib_head.read())

    def test_source_is_file(self):
        with open(win32.API_SOURCE, "rb") as source:
            with open(sibpath(win32.__file__, "win32.c"), "rb") as sib_src:
                self.assertEqual(source.read(), sib_src.read())

    def test_ffi(self):
        if os.name == "nt":
            self.assertIsInstance(win32._ffi, FFI)
            self.assertTrue(win32._ffi._windows_unicode)
        else:
            self.assertIs(win32._ffi, NotImplemented)

    def test_lib(self):
        if os.name == "nt":
            self.assertIsNot(win32._ffi, NotImplemented)
        else:
            self.assertIs(win32._ffi, NotImplemented)


class LoadFunctionTests(unittest.TestCase):
    """
    Tests for L{twisted.python.win32.get_library}.
    """
    def setUp(self):
        self.calls = []

    def capture_call(self, *args, **kwargs):
        self.calls.append((kwargs.pop("call_name", None), args, kwargs))

    def ignore_call(self, *args, **kwargs):
        pass

    def test_sets_unicode(self):
        self.patch(FFI, "cdef", self.ignore_call)
        self.patch(FFI, "verify", self.ignore_call)
        self.patch(FFI, "set_unicode", self.capture_call)
        win32.get_library(win32.API_HEADER, win32.API_SOURCE)
        self.assertEqual(self.calls, [(None, (True,), {})])

    def test_loads_source(self):
        self.patch(FFI, "set_unicode", self.ignore_call)
        self.patch(FFI, "verify", self.ignore_call)
        self.patch(FFI, "cdef", partial(self.capture_call, call_name="cdef"))
        win32.get_library(win32.API_HEADER, win32.API_SOURCE)
        self.assertEqual(
            self.calls, [
                ("cdef",
                 (open(sibpath(win32.__file__, "win32.c"), "rb").read(),), {})
            ]
        )

    def test_loads_header(self):
        self.patch(FFI, "set_unicode", self.ignore_call)
        self.patch(FFI, "cdef", self.ignore_call)
        self.patch(
            FFI, "verify", partial(self.capture_call, call_name="verify"))
        win32.get_library(win32.API_HEADER, win32.API_SOURCE)
        self.assertEqual(
            self.calls, [
                ("verify",
                 (open(sibpath(win32.__file__, "win32.h"), "rb").read(),),
                 {"libraries": ["kernel32"]})
            ]
        )

    def test_cdef_verify_call_order(self):
        """
        Order matters when calling ffi.cdef and ffi.verify.  If the order is
        incorrect the underlying library may still compile but not produce
        something the rest of win32.py can use.
        """
        self.patch(FFI, "set_unicode", self.ignore_call)
        self.patch(FFI, "cdef", partial(self.capture_call, call_name="cdef"))
        self.patch(
            FFI, "verify", partial(self.capture_call, call_name="verify"))
        win32.get_library(win32.API_HEADER, win32.API_SOURCE)
        self.assertEqual(["cdef", "verify"], [call[0] for call in self.calls])

    def test_return_value(self):
        self.patch(FFI, "set_unicode", self.ignore_call)
        self.patch(FFI, "cdef", self.ignore_call)
        self.patch(FFI, "verify", lambda *args, **kwargs: True)
        result = win32.get_library(win32.API_HEADER, win32.API_SOURCE)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], FFI)
        self.assertTrue(result[1])

