import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  type CallToolResult,
} from '@modelcontextprotocol/sdk/types.js'
import { Schift } from '@schift-io/sdk'

type SearchSource = 'bm25' | 'vector' | 'graphrag' | 'both'

type VaultNote = {
  title: string
  slug: string
  path: string
  body: string
  raw: string
  normalizedTitle: string
  normalizedBody: string
  compactTitle: string
  compactBody: string
  date: string | null
}

type SearchResult = {
  title: string
  slug: string
  snippet: string
  score: number
  source: SearchSource
}

type ContextResult = {
  _instructions?: string
  context: string
  sources: Array<{ title: string; slug: string }>
}

type GraphEntity = {
  id: string
  name: string
  type: string | null
  description: string | null
  source_note: string | null
}

type GraphRelationship = {
  source: string
  sourceType: string | null
  target: string
  targetType: string | null
  relationshipType: string | null
}

type SqliteStatement = {
  all: (...params: unknown[]) => unknown[]
}

type SqliteDatabase = {
  prepare: (sql: string) => SqliteStatement
  close: () => void
}

const DEFAULT_TOP_K = 10
const CONTEXT_TOP_K = 5
const MAX_NOTE_BODY_CHARS = 2000
const MAX_CONTEXT_CHARS = 12000
const WIKILINK_REGEX = /\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]/g
const TEMPORAL_QUERY_KEYWORDS = ['최근', '오늘', '어제', '최신', '방금', 'today', 'yesterday', 'latest', 'recent']
const GRAPHRAG_API_URL = process.env.GRAPHRAG_API_URL?.trim() || 'http://127.0.0.1:8400'
const GRAPHRAG_MODE = (process.env.GRAPHRAG_MODE?.trim() || 'primary').toLowerCase()
const GRAPHRAG_TIMEOUT_MS = Number(process.env.GRAPHRAG_TIMEOUT_MS) || 15000

let cachedNotes: VaultNote[] | null = null
let cachedAt = 0

function normalizeText(value: string): string {
  return value
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[._-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function compactText(value: string): string {
  return normalizeText(value).replace(/\s+/g, '')
}

function splitTerms(value: string): string[] {
  return normalizeText(value)
    .split(/[^\p{L}\p{N}]+/u)
    .map(term => term.trim())
    .filter(Boolean)
}

function asSlugFromPath(filePath: string, vaultPath: string): string {
  return path.relative(vaultPath, filePath).replace(/\\/g, '/').replace(/\.md$/i, '')
}

function basenameSlug(slug: string): string {
  const parts = slug.split('/')
  return parts[parts.length - 1] ?? slug
}

function parseDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null
  }

  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) {
    return null
  }

  const [, year, month, day] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day))
  return Number.isNaN(date.getTime()) ? null : date
}

function getDayDifference(from: Date, to: Date): number {
  const fromDate = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  const toDate = new Date(to.getFullYear(), to.getMonth(), to.getDate())
  const msPerDay = 24 * 60 * 60 * 1000
  return Math.floor((toDate.getTime() - fromDate.getTime()) / msPerDay)
}

function getRecencyBoost(date: string | null, query: string): number {
  const parsed = parseDate(date)
  if (!parsed) {
    return 1
  }

  const dayDifference = getDayDifference(parsed, new Date())
  let boost = 1

  if (dayDifference === 0) {
    boost = 2
  } else if (dayDifference === 1) {
    boost = 1.5
  } else if (dayDifference >= 2 && dayDifference <= 3) {
    boost = 1.2
  }

  const normalizedQuery = normalizeText(query)
  const hasTemporalKeyword = TEMPORAL_QUERY_KEYWORDS.some(keyword =>
    normalizedQuery.includes(normalizeText(keyword))
  )

  return hasTemporalKeyword && boost > 1 ? boost * 1.5 : boost
}

function countOccurrences(text: string, needle: string): number {
  if (!needle) {
    return 0
  }

  let count = 0
  let offset = 0

  while (offset < text.length) {
    const found = text.indexOf(needle, offset)
    if (found === -1) {
      break
    }
    count += 1
    offset = found + needle.length
  }

  return count
}

function buildSnippet(body: string, query: string): string {
  const compactQuery = compactText(query)
  const normalizedBody = normalizeText(body)
  const firstTerm = splitTerms(query)[0] ?? ''

  const hitIndex = firstTerm ? normalizedBody.indexOf(firstTerm) : -1
  const start = Math.max(0, hitIndex > -1 ? hitIndex - 80 : 0)
  const end = Math.min(body.length, start + 220)
  const snippet = body
    .slice(start, end)
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (snippet) {
    return `${start > 0 ? '...' : ''}${snippet}${end < body.length ? '...' : ''}`
  }

  return compactQuery ? `${body.slice(0, 220).replace(/\s+/g, ' ').trim()}...` : body.slice(0, 220)
}

function walkMarkdownFiles(dirPath: string): string[] {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name)
    let resolved = entry
    if (entry.isSymbolicLink()) {
      try {
        const stat = fs.statSync(fullPath)
        if (stat.isDirectory()) {
          files.push(...walkMarkdownFiles(fullPath))
          continue
        }
        if (stat.isFile() && fullPath.endsWith('.md')) {
          files.push(fullPath)
        }
        continue
      } catch {
        continue
      }
    }

    if (resolved.isDirectory()) {
      files.push(...walkMarkdownFiles(fullPath))
      continue
    }

    if (resolved.isFile() && fullPath.endsWith('.md')) {
      files.push(fullPath)
    }
  }

  return files
}

function getVaultPath(): string {
  const vaultPath = process.env.VAULT_PATH?.trim()
  if (!vaultPath) {
    throw new Error('VAULT_PATH is required')
  }

  if (!fs.existsSync(vaultPath) || !fs.statSync(vaultPath).isDirectory()) {
    throw new Error(`VAULT_PATH does not exist or is not a directory: ${vaultPath}`)
  }

  return vaultPath
}

function loadVaultNotes(): VaultNote[] {
  if (cachedNotes && Date.now() - cachedAt < 5000) {
    return cachedNotes
  }

  const vaultPath = getVaultPath()
  const files = walkMarkdownFiles(vaultPath)

  const notes = files.flatMap((filePath): VaultNote[] => {
    const raw = fs.readFileSync(filePath, 'utf8')
    let parsedData: Record<string, unknown> = {}
    let parsedContent = raw
    try {
      const parsed = matter(raw)
      parsedData = parsed.data
      parsedContent = parsed.content
    } catch (err) {
      console.error(`[vault-search] frontmatter parse failed for ${filePath}, using raw content`)
    }
    const stat = fs.statSync(filePath)
    const title =
      typeof parsedData.title === 'string' && parsedData.title.trim()
        ? parsedData.title.trim()
        : path.basename(filePath, '.md')
    const body = parsedContent.trim()
    const date =
      typeof parsedData.date === 'string'
        ? parsedData.date
        : stat.mtime.toISOString().slice(0, 10)

    return [{
      title,
      slug: asSlugFromPath(filePath, vaultPath),
      path: filePath,
      body,
      raw,
      normalizedTitle: normalizeText(title),
      normalizedBody: normalizeText(body),
      compactTitle: compactText(title),
      compactBody: compactText(body),
      date,
    }]
  })

  cachedNotes = notes
  cachedAt = Date.now()
  return notes
}

function scoreBm25(note: VaultNote, query: string): number {
  const queryTerms = splitTerms(query)
  if (queryTerms.length === 0) {
    return 0
  }

  let score = 0

  for (const term of queryTerms) {
    const compactTerm = term.replace(/\s+/g, '')

    if (note.normalizedTitle.includes(term) || note.compactTitle.includes(compactTerm)) {
      score += 10
    }

    score += countOccurrences(note.normalizedBody, term)

    if (compactTerm && compactTerm !== term) {
      score += countOccurrences(note.compactBody, compactTerm)
    }
  }

  return score * getRecencyBoost(note.date, query)
}

function bm25Search(query: string, topK = DEFAULT_TOP_K): SearchResult[] {
  const notes = loadVaultNotes()
  const results = notes
    .map(note => ({
      title: note.title,
      slug: note.slug,
      snippet: buildSnippet(note.body, query),
      score: scoreBm25(note, query),
      source: 'bm25' as const,
    }))
    .filter(result => result.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, topK)

  return results
}

async function vectorSearch(query: string, topK = DEFAULT_TOP_K): Promise<SearchResult[]> {
  const apiKey = process.env.SCHIFT_API_KEY?.trim()
  if (!apiKey) {
    return []
  }

  const collection = process.env.SCHIFT_BUCKET?.trim() || 'akwiki'
  const client = new Schift({ apiKey })
  let results

  try {
    results = await client.search({
      collection,
      query,
      topK,
      mode: 'hybrid',
      rerank: true,
    })
  } catch (error) {
    console.error('Schift search unavailable, falling back to BM25 only:', error)
    return []
  }

  return results.map(result => {
    const metadata = result.metadata ?? {}
    const rawTitle = metadata.title ?? metadata.name ?? metadata.source_note ?? result.id
    const title = typeof rawTitle === 'string' ? rawTitle : String(rawTitle)
    const rawSlug = metadata.slug ?? metadata.path ?? title
    const slug = typeof rawSlug === 'string' ? String(rawSlug).replace(/\.md$/i, '') : title
    const text = typeof metadata.snippet === 'string' ? metadata.snippet : ''

    return {
      title,
      slug,
      snippet: text || '',
      score: result.score,
      source: 'vector' as const,
    }
  })
}

function mergeResults(bm25Results: SearchResult[], vectorResults: SearchResult[], topK = DEFAULT_TOP_K): SearchResult[] {
  const merged = new Map<string, SearchResult>()

  for (const result of [...bm25Results, ...vectorResults]) {
    const key = normalizeText(result.title)
    const existing = merged.get(key)

    if (!existing) {
      merged.set(key, { ...result })
      continue
    }

    existing.score = Math.max(existing.score, result.score)
    existing.snippet = existing.snippet.length >= result.snippet.length ? existing.snippet : result.snippet
    existing.slug = existing.slug || result.slug
    existing.source =
      existing.source === result.source ? existing.source : 'both'
  }

  return [...merged.values()]
    .sort((left, right) => right.score - left.score)
    .slice(0, topK)
}

async function graphragSearch(query: string, topK = DEFAULT_TOP_K): Promise<SearchResult[]> {
  if (GRAPHRAG_MODE === 'disabled') {
    return []
  }

  const url = new URL('/api/search', GRAPHRAG_API_URL)
  url.searchParams.set('q', query)
  url.searchParams.set('mode', 'hybrid')
  url.searchParams.set('top_k', String(topK))
  url.searchParams.set('rerank', 'true')

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), GRAPHRAG_TIMEOUT_MS)

  try {
    const response = await fetch(url, { signal: controller.signal })
    if (!response.ok) {
      console.error(`[vault-search] GraphRAG HTTP ${response.status}`)
      return []
    }

    const payload = (await response.json()) as {
      results?: Array<{
        entity?: string | null
        name?: string | null
        source_note?: string | null
        description?: string | null
        type?: string | null
        score?: number
      }>
      search_type?: string
    }

    const items = Array.isArray(payload.results) ? payload.results : []
    return items
      .map((item, index): SearchResult => {
        const rawTitle = item.entity || item.name || item.source_note || `result-${index + 1}`
        const title = String(rawTitle)
        const sourceNote = item.source_note || title
        const slug = String(sourceNote).replace(/\.md$/i, '')
        const description = typeof item.description === 'string' ? item.description : ''
        const snippet = description.length > 0
          ? description.slice(0, 220)
          : `${item.type ? `[${item.type}] ` : ''}${title}`

        return {
          title,
          slug,
          snippet,
          score: typeof item.score === 'number' ? item.score : 0,
          source: 'graphrag' as const,
        }
      })
      .slice(0, topK)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.error(`[vault-search] GraphRAG unavailable: ${message}`)
    return []
  } finally {
    clearTimeout(timeout)
  }
}

async function runVaultSearch(query: string, topK = DEFAULT_TOP_K): Promise<SearchResult[]> {
  if (GRAPHRAG_MODE === 'primary') {
    const graphragResults = await graphragSearch(query, topK)
    if (graphragResults.length > 0) {
      console.error(`[vault-search] graphrag=${graphragResults.length} (primary)`)
      return graphragResults
    }
    console.error('[vault-search] GraphRAG empty, falling back to BM25+vector')
  }

  const bm25Results = bm25Search(query, topK)

  try {
    const vectorResults = await vectorSearch(query, topK)
    console.error(`[vault-search] bm25=${bm25Results.length} vector=${vectorResults.length}`)
    if (vectorResults.length > 0) {
      console.error(`[vault-search] first vector score=${vectorResults[0].score} source=${vectorResults[0].source}`)
    }

    if (GRAPHRAG_MODE === 'merge') {
      const graphragResults = await graphragSearch(query, topK)
      console.error(`[vault-search] graphrag=${graphragResults.length} (merge)`)
      return mergeResults(mergeResults(bm25Results, vectorResults, topK), graphragResults, topK)
    }

    return mergeResults(bm25Results, vectorResults, topK)
  } catch (error) {
    console.error('Schift search unavailable, falling back to BM25 only:', error)
    return bm25Results
  }
}

function findNoteByReference(reference: string, notes: VaultNote[]): VaultNote | null {
  const normalizedReference = normalizeText(reference)
  const compactReference = compactText(reference)

  for (const note of notes) {
    if (
      note.normalizedTitle === normalizedReference ||
      note.compactTitle === compactReference ||
      normalizeText(note.slug) === normalizedReference ||
      compactText(note.slug) === compactReference ||
      normalizeText(basenameSlug(note.slug)) === normalizedReference ||
      compactText(basenameSlug(note.slug)) === compactReference
    ) {
      return note
    }
  }

  return null
}

function extractWikilinks(note: VaultNote, notes: VaultNote[]): VaultNote[] {
  const found = new Map<string, VaultNote>()

  for (const match of note.raw.matchAll(WIKILINK_REGEX)) {
    const target = match[1]?.trim()
    if (!target) {
      continue
    }

    const linkedNote = findNoteByReference(target, notes)
    if (linkedNote) {
      found.set(linkedNote.slug, linkedNote)
    }
  }

  return [...found.values()]
}

function getDbPath(): string | null {
  const configured = process.env.GRAPHRAG_DB_PATH?.trim()
  if (configured) {
    return configured
  }

  const vaultPath = process.env.VAULT_PATH?.trim()
  if (!vaultPath) {
    return null
  }

  return path.join(vaultPath, 'vault_graph.db')
}

async function openGraphDb(): Promise<SqliteDatabase | null> {
  const dbPath = getDbPath()
  if (!dbPath || !fs.existsSync(dbPath)) {
    return null
  }

  try {
    const module = await import('better-sqlite3')
    const Database = module.default
    return new Database(dbPath, { readonly: true, fileMustExist: true }) as SqliteDatabase
  } catch (error) {
    console.error('better-sqlite3 unavailable, GraphRAG features disabled:', error)
    return null
  }
}

function getTableNames(db: SqliteDatabase): Set<string> {
  const rows = db
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table'")
    .all() as Array<{ name: string }>

  return new Set(rows.map(row => row.name))
}

function getEntityMatches(db: SqliteDatabase, entity: string): GraphEntity[] {
  const sql = `
    SELECT id, name, type, description, source_note
    FROM entities
    WHERE lower(name) = lower(?)
       OR lower(name) LIKE lower(?)
       OR lower(source_note) LIKE lower(?)
    ORDER BY
      CASE WHEN lower(name) = lower(?) THEN 0 ELSE 1 END,
      length(name) ASC
    LIMIT 5
  `

  return db.prepare(sql).all(entity, `%${entity}%`, `%${entity}%`, entity) as GraphEntity[]
}

function getRelationshipsForEntity(db: SqliteDatabase, entityId: string): GraphRelationship[] {
  const sql = `
    SELECT
      source.name AS source,
      source.type AS sourceType,
      target.name AS target,
      target.type AS targetType,
      relationships.type AS relationshipType
    FROM relationships
    JOIN entities AS source ON source.id = relationships.source_id
    JOIN entities AS target ON target.id = relationships.target_id
    WHERE relationships.source_id = ? OR relationships.target_id = ?
    LIMIT 50
  `

  return db.prepare(sql).all(entityId, entityId) as GraphRelationship[]
}

function getTwoHopRelationships(db: SqliteDatabase, neighborNames: string[]): GraphRelationship[] {
  if (neighborNames.length === 0) {
    return []
  }

  const placeholders = neighborNames.map(() => '?').join(', ')
  const sql = `
    SELECT
      source.name AS source,
      source.type AS sourceType,
      target.name AS target,
      target.type AS targetType,
      relationships.type AS relationshipType
    FROM relationships
    JOIN entities AS source ON source.id = relationships.source_id
    JOIN entities AS target ON target.id = relationships.target_id
    WHERE source.name IN (${placeholders}) OR target.name IN (${placeholders})
    LIMIT 75
  `

  return db.prepare(sql).all(...neighborNames, ...neighborNames) as GraphRelationship[]
}

function getCommunityInfo(db: SqliteDatabase, entityId: string): string[] {
  const tableNames = getTableNames(db)
  const lines: string[] = []

  if (tableNames.has('entities') && tableNames.has('communities')) {
    const sql = `
      SELECT communities.name AS name, communities.summary AS summary, communities.level AS level
      FROM entities
      JOIN communities ON communities.id = entities.community_id
      WHERE entities.id = ?
      LIMIT 10
    `

    const rows = db.prepare(sql).all(entityId) as Array<{ name: string | null; summary: string | null; level: number | null }>
    for (const row of rows) {
      const levelTag = row.level !== null ? ` [L${row.level}]` : ''
      lines.push(`${row.name ?? 'Unnamed community'}${levelTag}${row.summary ? `: ${row.summary}` : ''}`)
    }
  }

  return lines
}

async function getGraphForEntity(entity: string) {
  const db = await openGraphDb()
  if (!db) {
    return {
      found: false,
      message: 'GraphRAG database not found. Set GRAPHRAG_DB_PATH or place vault_graph.db in the vault root.',
      matches: [] as GraphEntity[],
      oneHop: [] as GraphRelationship[],
      twoHop: [] as GraphRelationship[],
      communities: [] as string[],
    }
  }

  try {
    const matches = getEntityMatches(db, entity)
    if (matches.length === 0) {
      return {
        found: false,
        message: `No GraphRAG entity match found for "${entity}".`,
        matches,
        oneHop: [] as GraphRelationship[],
        twoHop: [] as GraphRelationship[],
        communities: [] as string[],
      }
    }

    const primary = matches[0]
    const oneHop = getRelationshipsForEntity(db, primary.id)
    const neighborNames = [...new Set(oneHop.flatMap(rel => [rel.source, rel.target]).filter(name => normalizeText(name) !== normalizeText(primary.name)))]
    const twoHop = getTwoHopRelationships(db, neighborNames)
      .filter(rel => rel.source !== primary.name && rel.target !== primary.name)
      .slice(0, 50)
    const communities = getCommunityInfo(db, primary.id)

    return {
      found: true,
      message: `Graph match for "${primary.name}".`,
      matches,
      oneHop,
      twoHop,
      communities,
    }
  } finally {
    db.close()
  }
}

async function getGraphContextForNote(note: VaultNote): Promise<string[]> {
  const graph = await getGraphForEntity(note.title)
  if (!graph.found) {
    return []
  }

  const lines: string[] = []
  lines.push(`Graph entity: ${graph.matches[0]?.name}`)

  if (graph.matches[0]?.description) {
    lines.push(`Description: ${graph.matches[0].description}`)
  }

  for (const rel of graph.oneHop.slice(0, 8)) {
    lines.push(`${rel.source} -[${rel.relationshipType ?? 'related_to'}]-> ${rel.target}`)
  }

  for (const community of graph.communities.slice(0, 3)) {
    lines.push(`Community: ${community}`)
  }

  return lines
}

async function runVaultContext(query: string): Promise<ContextResult> {
  const notes = loadVaultNotes()
  const searchResults = await runVaultSearch(query, DEFAULT_TOP_K)
  const selected = searchResults.slice(0, CONTEXT_TOP_K)
  const sources = new Map<string, { title: string; slug: string }>()
  const sections: string[] = []

  for (const result of selected) {
    const note = findNoteByReference(result.slug, notes) ?? findNoteByReference(result.title, notes)
    if (!note) {
      continue
    }

    sources.set(note.slug, { title: note.title, slug: note.slug })
    sections.push(`## ${note.title}`)
    sections.push(`Slug: ${note.slug}`)
    sections.push(`Search score: ${result.score.toFixed(3)} (${result.source})`)
    const trimmedBody = note.body.trim()
    const truncatedBody = trimmedBody.length > MAX_NOTE_BODY_CHARS
      ? `${trimmedBody.slice(0, MAX_NOTE_BODY_CHARS)}... [truncated]`
      : trimmedBody
    sections.push(truncatedBody)

    const linkedNotes = extractWikilinks(note, notes).slice(0, 5)
    if (linkedNotes.length > 0) {
      sections.push('Connected notes:')
      for (const linked of linkedNotes) {
        sources.set(linked.slug, { title: linked.title, slug: linked.slug })
        sections.push(`- ${linked.title} (${linked.slug})`)
        sections.push(linked.body.slice(0, 400).replace(/\s+/g, ' ').trim())
      }
    }

    const graphLines = await getGraphContextForNote(note)
    if (graphLines.length > 0) {
      sections.push('Graph context:')
      sections.push(...graphLines.map(line => `- ${line}`))
    }

    sections.push('')
  }

  const context = sections.join('\n').trim()
  const truncatedContext = context.length > MAX_CONTEXT_CHARS
    ? `${context.slice(0, MAX_CONTEXT_CHARS)}\n\n[Context truncated to fit token limit]`
    : context

  return {
    _instructions: 'This payload is reference material for you to read silently. Do NOT echo the raw context or sources back to the user. Synthesize a natural-language answer based on `context`, citing notes by `[title]` from `sources`. Only paste fragments verbatim if the user explicitly asks.',
    context: truncatedContext,
    sources: [...sources.values()],
  }
}

function formatJsonResult(value: unknown): CallToolResult {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(value, null, 2),
      },
    ],
  }
}

function formatError(message: string): CallToolResult {
  return {
    content: [
      {
        type: 'text',
        text: message,
      },
    ],
    isError: true,
  }
}

function getStringArg(value: unknown, name: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`${name} must be a non-empty string`)
  }

  return value.trim()
}

function getNumberArg(value: unknown, fallback: number): number {
  if (value === undefined) {
    return fallback
  }

  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error('topK must be a finite number')
  }

  return Math.max(1, Math.floor(value))
}

export function createVaultSearchServer(): Server {
  const server = new Server(
    {
      name: 'vault-search-mcp',
      version: '0.1.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  )

  registerHandlers(server)
  return server
}

function registerHandlers(server: Server): void {
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    // ChatGPT-required tools (exact names per OpenAI Apps SDK MCP spec)
    {
      name: 'search',
      description:
        'Search the personal vault for notes matching a natural-language query. Returns a list of {id, title, url} entries. Use the id with `fetch` to get full note content.',
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Natural-language search query.',
          },
        },
        required: ['query'],
      },
    },
    {
      name: 'fetch',
      description:
        'Fetch the full content of a vault note by its id (returned by `search`). Returns {id, title, text, url, metadata} where text is the full markdown body.',
      inputSchema: {
        type: 'object',
        properties: {
          id: {
            type: 'string',
            description: 'Note id (slug) returned by the `search` tool.',
          },
        },
        required: ['id'],
      },
    },
    // Original vault tools (used by Codex/Claude Code, kept for backward compat)
    {
      name: 'vault_search',
      description:
        'Search the vault with BM25 and optional Schift hybrid vector search, then merge and dedupe the results.',
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'User query to search for in the vault.',
          },
          topK: {
            type: 'number',
            description: 'Maximum number of results to return.',
            default: DEFAULT_TOP_K,
          },
        },
        required: ['query'],
      },
    },
    {
      name: 'vault_context',
      description:
        'Build LLM-ready context from the top vault search results, linked notes, and GraphRAG relationships when available.',
      inputSchema: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Query used to gather context from the vault.',
          },
        },
        required: ['query'],
      },
    },
    {
      name: 'vault_graph',
      description:
        'Query the GraphRAG database for an entity, returning fuzzy matches, one-hop and two-hop relationships, and community information.',
      inputSchema: {
        type: 'object',
        properties: {
          entity: {
            type: 'string',
            description: 'Entity name to look up in the GraphRAG database.',
          },
        },
        required: ['entity'],
      },
    },
  ],
}))

  server.setRequestHandler(CallToolRequestSchema, async request => {
    try {
      const args = (request.params.arguments ?? {}) as Record<string, unknown>

      switch (request.params.name) {
        case 'search': {
          // ChatGPT-required tool: input {query: string} → output {results: [{id, title, url}]}
          const query = getStringArg(args.query, 'query')
          const results = await runVaultSearch(query, DEFAULT_TOP_K)
          const vaultName = path.basename(getVaultPath())
          const chatgptResults = results.map(result => ({
            id: result.slug,
            title: result.title,
            url: `obsidian://open?vault=${encodeURIComponent(vaultName)}&file=${encodeURIComponent(result.slug)}`,
          }))
          return {
            content: [
              {
                type: 'text' as const,
                text: JSON.stringify({ results: chatgptResults }),
              },
            ],
          }
        }

        case 'fetch': {
          // ChatGPT-required tool: input {id: string} → output {id, title, text, url, metadata}
          const id = getStringArg(args.id, 'id')
          const notes = loadVaultNotes()
          const note = findNoteByReference(id, notes)
          if (!note) {
            return formatError(`note not found: ${id}`)
          }
          const vaultName = path.basename(getVaultPath())
          const truncatedText = note.body.length > MAX_CONTEXT_CHARS
            ? `${note.body.slice(0, MAX_CONTEXT_CHARS)}\n\n[truncated]`
            : note.body
          const fetchResult = {
            id: note.slug,
            title: note.title,
            text: truncatedText,
            url: `obsidian://open?vault=${encodeURIComponent(vaultName)}&file=${encodeURIComponent(note.slug)}`,
            metadata: {
              slug: note.slug,
              date: note.date,
              source: 'vault-search-mcp',
            },
          }
          return {
            content: [
              {
                type: 'text' as const,
                text: JSON.stringify(fetchResult),
              },
            ],
          }
        }

        case 'vault_search': {
          const query = getStringArg(args.query, 'query')
          const topK = getNumberArg(args.topK, DEFAULT_TOP_K)
          const results = await runVaultSearch(query, topK)
          return formatJsonResult({
            _instructions: 'Candidate vault notes ranked by hybrid score. Use them to pick the most relevant note(s), then call `vault_context` for full content. Do NOT dump this list verbatim — synthesize.',
            query,
            results,
          })
        }

        case 'vault_context': {
          const query = getStringArg(args.query, 'query')
          const context = await runVaultContext(query)
          return formatJsonResult(context)
        }

        case 'vault_graph': {
          const entity = getStringArg(args.entity, 'entity')
          const graph = await getGraphForEntity(entity)
          return formatJsonResult({
            _instructions: 'GraphRAG entity neighborhood. Summarize relationships and community membership in natural language; cite entity names. Do NOT dump the raw edge list unless the user asks.',
            entity,
            ...graph,
          })
        }

        default:
          return formatError(`Unknown tool: ${request.params.name}`)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      return formatError(message)
    }
  })
}

async function main() {
  const server = createVaultSearchServer()
  const transport = new StdioServerTransport()
  await server.connect(transport)
  console.error('vault-search-mcp server running on stdio')
}

const ENTRY_URL = `file://${process.argv[1]}`
if (import.meta.url === ENTRY_URL) {
  main().catch(error => {
    console.error('Failed to start vault-search-mcp:', error)
    process.exit(1)
  })
}
