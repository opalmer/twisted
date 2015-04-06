import os
from cffi import FFI

ffi = FFI()
ffi.cdef('''
typedef unsigned long DWORD;
typedef void *PVOID;
typedef PVOID HANDLE;
typedef HANDLE *PHANDLE;
#define GMEM_MOVEABLE ...
int anonymous_pipe(int * reader, int * writer);
void * malloc(size_t);
void free(void*);
''')

_lib = ffi.verify('''
    #include <windows.h>
    #include <io.h>
    #include <fcntl.h>

    int anonymous_pipe(int * reader, int * writer) {
        int ok;
        HANDLE read_pipe;
        HANDLE write_pipe;

        SECURITY_ATTRIBUTES security_attrs = {
            sizeof(SECURITY_ATTRIBUTES), 0, TRUE
        };

        ok = CreatePipe(&read_pipe, &write_pipe, &security_attrs, 0);

        *reader = _open_osfhandle((INT_PTR)read_pipe, O_BINARY);
        *writer = _open_osfhandle((INT_PTR)write_pipe, O_BINARY);
        return ok;
    };
''', libraries=["kernel32"])


def create_anonymous_pipe():
    int_size = ffi.new("int *")
    p_reader = ffi.cast("int *", _lib.malloc(ffi.sizeof(int_size)))
    p_writer = ffi.cast("int *", _lib.malloc(ffi.sizeof(int_size)))
    result = _lib.anonymous_pipe(p_reader, p_writer)
    errno, error_string = ffi.getwinerror(result)
    print errno, error_string

    fd_reader = p_reader[0]
    fd_writer = p_writer[0]
    print fd_reader, fd_writer
    _lib.free(p_reader)
    _lib.free(p_writer)

    # a = os.fdopen(fd_reader, "w")
    # a.write("reader")
    # a.close()
    # b = os.fdopen(fd_writer, "w")
    # b.write("writer")
    # b.close()
    return fd_reader, fd_writer


create_anonymous_pipe()
create_anonymous_pipe()