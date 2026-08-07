// Unix-domain-socket peer credential verification.
//
// `primary.sock` being mode 0600 (see server.ts `startIpcServer`) already
// means the filesystem itself refuses connect() from any other local user
// — that's the OS enforcing it, not us. This module is the second,
// independent gate the spec calls for: even if the socket briefly had
// looser permissions (a stale file from a prior run, a surprising umask,
// a root process that ignores file perms), we still refuse to talk to a
// peer whose effective uid isn't our own.
//
// macOS/BSD expose this via the `getpeereid(3)` libc call, which is exactly
// what we need ("get the effective user ID of a UNIX-domain socket peer")
// and is a plain libc symbol with a simple two-out-param signature.
//
// Linux does not have `getpeereid(3)` in glibc; the equivalent is the
// `SO_PEERCRED` socket option read via `getsockopt(2)`, which fills a
// `struct ucred { pid_t pid; uid_t uid; gid_t gid; }` — three 4-byte
// (LP64) ints, 12 bytes, no padding. `SOL_SOCKET` = 1 and `SO_PEERCRED`
// = 17 are the values from `asm-generic/socket.h`, which is what x86_64
// and arm64 Linux use (the handful of architectures with their own
// socket.h — alpha, mips, parisc, sparc — renumber these constants, but
// none of them are a WSL2/Ubuntu/Debian/desktop-Linux student target).
// Both `getsockopt` and `SO_PEERCRED` are plain glibc/libc symbols, no
// libbsd dependency required.
//
// Node's `net` module does not expose peer credentials or a documented raw
// fd accessor. `socket._handle.fd` is undocumented but stable in practice
// (it's how the handful of existing `getpeercred`-style npm packages do
// it too) and is the only way to get an fd to hand to the FFI call.

import koffi from 'koffi';
import type { LibraryHandle } from 'koffi';
import { platform } from 'node:os';

type GetPeerEid = (fd: number, euid: number[], egid: number[]) => number;

// `struct ucred` marshaled as a JS object by koffi (`_Out_` struct
// pointer) — see the POSIX `gettimeofday` pattern in koffi's own docs
// (doc/output.md) for the same "empty object in, filled object out" shape.
interface Ucred {
  pid?: number;
  uid?: number;
  gid?: number;
}

type GetSockOpt = (fd: number, level: number, optname: number, optval: Ucred, optlen: number[]) => number;

// asm-generic/socket.h (x86_64 / arm64 Linux, including WSL2).
const SOL_SOCKET = 1;
const SO_PEERCRED = 17;

let getpeereid: GetPeerEid | null = null;
let getsockoptPeercred: GetSockOpt | null = null;
let ucredSize = 12; // sizeof(struct ucred): 3 x int32, no padding — overwritten below once the Linux struct type is registered, kept as a documented fallback constant otherwise.

if (platform() === 'darwin') {
  const libc = koffi.load('/usr/lib/libSystem.B.dylib');
  // Cast through `unknown`: koffi's own return type for `.func()` is a
  // generic callable, not our specific (fd, euid, egid) => number shape.
  getpeereid = libc.func('int getpeereid(int fd, _Out_ uint32 *euid, _Out_ uint32 *egid)') as unknown as GetPeerEid;
} else if (platform() === 'linux') {
  // `libc.so.6` is the versioned glibc soname present on every glibc-based
  // distro (Ubuntu/Debian under WSL2 included). `libc.so` is a fallback
  // for the rare musl-linked environment where the versioned name isn't
  // on the loader path.
  let libc: LibraryHandle | null = null;
  for (const candidate of ['libc.so.6', 'libc.so']) {
    try {
      libc = koffi.load(candidate);
      break;
    } catch {
      // try the next candidate name
    }
  }

  if (libc) {
    const UcredStruct = koffi.struct('ucred', {
      pid: 'int32_t',
      uid: 'uint32_t',
      gid: 'uint32_t',
    });
    ucredSize = koffi.sizeof(UcredStruct);
    getsockoptPeercred = libc.func(
      'int getsockopt(int fd, int level, int optname, _Out_ ucred *optval, _Inout_ uint32 *optlen)',
    ) as unknown as GetSockOpt;
  }
}

/**
 * Returns the effective UID of the process on the other end of a connected
 * AF_UNIX SOCK_STREAM socket, or `null` if it cannot be determined —
 * unsupported platform, the socket handle has no usable fd, or the libc
 * call itself failed. Callers MUST treat `null` as "reject the connection",
 * never as "allow" — see `verifyPeerIsSelf`.
 */
export function getPeerUid(fd: unknown): number | null {
  if (typeof fd !== 'number' || fd < 0) return null;

  if (getpeereid) {
    const euidOut: number[] = [0];
    const egidOut: number[] = [0];
    const rc = getpeereid(fd, euidOut, egidOut);
    if (rc !== 0) return null;
    return euidOut[0] ?? null;
  }

  if (getsockoptPeercred) {
    const optlen: number[] = [ucredSize];
    const ucredOut: Ucred = {};
    const rc = getsockoptPeercred(fd, SOL_SOCKET, SO_PEERCRED, ucredOut, optlen);
    if (rc !== 0) return null;
    return ucredOut.uid ?? null;
  }

  return null;
}

/**
 * Extracts the raw fd Node stashes on a connected `net.Socket`. Not part of
 * any public Node type, hence the narrow structural cast instead of `any`.
 */
export function socketFd(socket: unknown): unknown {
  return (socket as { _handle?: { fd?: unknown } })?._handle?.fd;
}

/**
 * True only if the peer's effective UID matches our own process's UID.
 * Fail-closed: any lookup failure (wrong platform, no fd, libc error)
 * returns false.
 */
export function verifyPeerIsSelf(socket: unknown): boolean {
  if (typeof process.getuid !== 'function') return false; // non-POSIX platform
  const peerUid = getPeerUid(socketFd(socket));
  return peerUid !== null && peerUid === process.getuid();
}
