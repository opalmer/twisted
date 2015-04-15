/*
 * Copyright (c) Twisted Matrix Laboratories.
 * See LICENSE for details.
 */

#include <windows.h>
#include <fcntl.h>

int open_handle(HANDLE handle, int mode) {
    return _open_osfhandle((INT_PTR)handle, mode);
};