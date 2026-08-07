// Minimal newline-delimited-JSON framer for the Unix socket IPC between
// server.ts and mcp.ts. TCP/Unix stream sockets don't preserve message
// boundaries, so each side buffers partial reads until a `\n` shows up.

export class LineReader {
  private buf = '';

  constructor(private readonly onLine: (line: string) => void) {}

  push(chunk: Buffer | string): void {
    this.buf += typeof chunk === 'string' ? chunk : chunk.toString('utf8');
    let idx = this.buf.indexOf('\n');
    while (idx !== -1) {
      const line = this.buf.slice(0, idx);
      this.buf = this.buf.slice(idx + 1);
      if (line.length > 0) this.onLine(line);
      idx = this.buf.indexOf('\n');
    }
  }
}
