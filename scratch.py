import os

from cffi import FFI
from twisted.python.win32 import quoteArguments

ffi = FFI()
ffi.set_unicode(True)

WIN32C = open("twisted/python/win32.c", "r").read()
WIN32H = open("twisted/python/win32.h", "r").read()

ffi.cdef(WIN32C)
_lib = ffi.verify(WIN32H, libraries=["kernel32"])


# TODO: documentation
def CreatePipe():
    # TODO: remove commented code, we may not be needing it...
    hReader = ffi.new("PHANDLE")
    hWriter = ffi.new("PHANDLE")
    security_attributes = ffi.new("SECURITY_ATTRIBUTES[]", 1)
    # security_attributes[0].nLength = ffi.sizeof(security_attributes)
    security_attributes[0].bInheritHandle = True
    # security_attributes[0].lpSecurityDescriptor = ffi.NULL

    ok = _lib.CreatePipe(hReader, hWriter, security_attributes, 0)
    if not ok:
        raise Exception(ffi.getwinerror())

    # assert _lib.open_handle(hReader[0], _lib._O_BINARY) != -1
    # assert _lib.open_handle(hWriter[0], _lib._O_BINARY) != -1

    return hReader[0], hWriter[0]


# TODO: documentation
def SetNamedPipeHandlerState(handle, state=None):
    if state is None:
        state = _lib.PIPE_NOWAIT

    state = ffi.new("LPDWORD", state)
    ok = _lib.SetNamedPipeHandleState(handle, state, ffi.NULL, ffi.NULL)

    if not ok:
        raise Exception(ffi.getwinerror())


# TODO: documentation
def CloseHandle(handle):
    ok = _lib.CloseHandle(handle)
    if not ok:
        raise Exception(ffi.getwinerror())


# TODO: documentation
def DuplicateHandle(source):
    current_process = _lib.GetCurrentProcess()
    target = ffi.new("LPHANDLE")
    ok = _lib.DuplicateHandle(
        current_process, source, current_process, target,
        0, 0, _lib.DUPLICATE_SAME_ACCESS
    )
    if not ok:
        raise Exception(ffi.getwinerror())

    return target[0]


# TODO: documentation, especially input expectations
def CreateProcess(command, hStdinR, hStdoutW, hStderrW, environment=None):
    if environment is None:
        environment = {}

    if not isinstance(environment, dict):
        raise TypeError("Expected a dictionary instance for `environ`")

    # Add the specified environment to the current environment - this is
    # necessary because certain operations are only supported on Windows
    # if certain environment variables are present.
    environment = dict(os.environ.items() + environment.items())

    # Convert the provided environment into keys and value separated
    # by the null terminator.  This is required by the CreateProcess() call
    # later on.
    built_environment = []
    for key, value in environment.items():
        # Per Microsoft's documentation on CreateProcess() environment keys
        # cannot contain equal signs.  We check this here so we don't have
        # interpret odd error codes from the APIs.
        if "=" in key:
            raise ValueError("Environment keys cannot contain '='")

        if "\0" in key:
            raise ValueError(
                "Unexpected null terminator '\0' found in environment "
                "key %r" % key)

        if "\0" in value:
            raise ValueError(
                "Unexpected null terminator '\0' found in environment "
                "value for %r" % key)

        built_environment.append("=".join([key, value]))

    joined_environment = "\0".join(built_environment)
    quote_command = quoteArguments(command)
    command = ffi.new(
        "TCHAR[%d]" % len(quote_command), unicode(quote_command))
    environment = ffi.new(
        "TCHAR[%d]" % len(joined_environment), unicode(joined_environment))

    startup_information = ffi.new("STARTUPINFO[]", 1)
    startup_information[0].hStdOutput = hStdoutW
    startup_information[0].hStdError = hStderrW
    startup_information[0].hStdInput = hStdinR
    startup_information[0].dwFlags = _lib.STARTF_USESTDHANDLES
    process_information = ffi.new("PROCESS_INFORMATION[]", 1)

    # TODO: impersonation? (spawnProcess does not do this on Windows right now)
    ok = _lib.CreateProcess(
        ffi.NULL,     # lpApplicationName
        command,      # lpCommandLine
        ffi.NULL,     # lpProcessAttributes
        ffi.NULL,     # lpThreadAttributes
        1,            # bInheritHandles
        _lib.CREATE_UNICODE_ENVIRONMENT,  # dwCreationFlags
        environment,  # lpEnvironment
        ffi.NULL,     # TODO: lpStartupInfo
        startup_information,
        process_information
    )

    if not ok:
        # TODO: https://twistedmatrix.com/trac/ticket/2787
        # TODO: https://twistedmatrix.com/trac/ticket/4184
        raise Exception(ffi.getwinerror())

    # wait for child to exit
    # TODO: remove this once done testing
    _lib.WaitForSingleObject(process_information[0].hProcess, _lib.INFINITE)

from twisted.python import winapi
# from os.path import isfile

# ffi, lib = winapi.load(winapi.API_HEADER, winapi.API_SOURCE)
print dir(winapi.lib)

#
# hStdoutR, hStdoutW = CreatePipe()
# hStderrR, hStderrW = CreatePipe()
# hStdinR, hStdinW = CreatePipe()
#
# SetNamedPipeHandlerState(hStdinW, state=_lib.PIPE_NOWAIT)
#
# tmp = DuplicateHandle(hStdoutR)
# CloseHandle(hStdoutR)
# hStdoutR = tmp
#
# tmp = DuplicateHandle(hStderrR)
# CloseHandle(hStdoutR)
# hStderrR = tmp
#
# tmp = DuplicateHandle(hStdinW)
# CloseHandle(hStdoutR)
# hStdinW = tmp
#
# CreateProcess(
#     ["ping", "-c", "2", "127.0.0.1"],
#     hStdinR, hStdoutR, hStdoutW
# )
#
