"""Linux network denial inherited by every conversion subprocess (libseccomp)."""
import ctypes
import ctypes.util
import errno
import resource
import socket

from .models import ConversionError


def restrict_worker(timeout: int) -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 ** 3, 2 * 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 5))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 ** 3, 4 * 1024 ** 3))
    name = ctypes.util.find_library("seccomp")
    if not name:
        raise ConversionError("Falta libseccomp: no se puede garantizar una conversión sin red.")
    lib = ctypes.CDLL(name, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    class Compare(ctypes.Structure):
        _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                    ("a", ctypes.c_uint64), ("b", ctypes.c_uint64)]
    ctx = lib.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise ConversionError("No se pudo crear la protección de red.")
    try:
        syscall = lib.seccomp_syscall_resolve_name(b"socket")
        # Deny every domain except AF_UNIX, including future/less usual network families.
        cmp = Compare(0, 1, socket.AF_UNIX, 0)  # SCMP_CMP_NE
        if lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, syscall, 1, cmp) < 0 or lib.seccomp_load(ctx) < 0:
            raise ConversionError("No se pudo activar la protección de red.")
    finally:
        lib.seccomp_release(ctx)

