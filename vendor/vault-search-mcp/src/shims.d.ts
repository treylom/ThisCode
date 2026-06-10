declare module 'better-sqlite3' {
  type Statement = {
    all: (...params: unknown[]) => unknown[]
  }

  class Database {
    constructor(path: string, options?: Record<string, unknown>)
    prepare(sql: string): Statement
    close(): void
  }

  export default Database
}
