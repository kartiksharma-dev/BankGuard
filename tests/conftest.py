import sys
import pytest

# On Windows in sandboxed/restricted environments without loopback TCP permissions,
# Python's socket.socketpair() hangs indefinitely inside BaseProactorEventLoop._make_self_pipe()
# because connect('127.0.0.1') is blocked and lsock.accept() waits forever.
# We configure Windows Proactor to use Overlapped Named Pipes instead, which use Windows kernel IPC
# with zero TCP/IP or network dependencies.
if sys.platform == "win32":
    import _winapi
    import _overlapped
    import signal
    import uuid
    from asyncio.proactor_events import BaseProactorEventLoop

    signal.set_wakeup_fd = lambda fd, **kw: -1

    class PipeHandle:
        def __init__(self, handle):
            self.handle = handle

        def fileno(self):
            return self.handle

        def setblocking(self, b):
            pass

        def send(self, data):
            ov = _overlapped.Overlapped()
            ov.WriteFile(self.handle, data)

        def close(self):
            try:
                _winapi.CloseHandle(self.handle)
            except Exception:
                pass

    def pipe_make_self_pipe(self):
        pipe_name = rf"\\.\pipe\asyncio_self_pipe_{uuid.uuid4().hex}"
        h_server = _winapi.CreateNamedPipe(
            pipe_name,
            _winapi.PIPE_ACCESS_DUPLEX | _winapi.FILE_FLAG_OVERLAPPED,
            0,
            1,
            4096,
            4096,
            0,
            0,
        )
        h_client = _winapi.CreateFile(
            pipe_name,
            _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
            0,
            0,
            _winapi.OPEN_EXISTING,
            _winapi.FILE_FLAG_OVERLAPPED,
            0,
        )
        self._ssock = PipeHandle(h_server)
        self._csock = PipeHandle(h_client)
        self._internal_fds += 1

    BaseProactorEventLoop._make_self_pipe = pipe_make_self_pipe
