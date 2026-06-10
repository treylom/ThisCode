import type { Request, Response, NextFunction } from 'express'
import { createRemoteJWKSet, jwtVerify, type JWTPayload } from 'jose'

export type AuthMode = 'oauth' | 'bearer' | 'none'
export type OAuthProvider = 'workos' | 'auth0' | null

const AUTHKIT_DOMAIN_RAW = process.env.WORKOS_AUTHKIT_DOMAIN?.trim() || ''
// Accept both "xxx.authkit.app" (hostname only — xmcp convention) and "https://xxx.authkit.app" (full URL)
const AUTHKIT_DOMAIN = AUTHKIT_DOMAIN_RAW
  ? (AUTHKIT_DOMAIN_RAW.startsWith('http')
      ? AUTHKIT_DOMAIN_RAW.replace(/\/+$/, '')
      : `https://${AUTHKIT_DOMAIN_RAW.replace(/\/+$/, '')}`)
  : ''
const WORKOS_AUDIENCE = process.env.WORKOS_AUDIENCE?.trim() || ''

const AUTH0_DOMAIN = process.env.AUTH0_DOMAIN?.trim() || ''
const AUTH0_AUDIENCE = process.env.AUTH0_AUDIENCE?.trim() || ''

const LEGACY_BEARER = process.env.MCP_AUTH_TOKEN?.trim() || ''
const RESOURCE_URL = process.env.MCP_RESOURCE_URL?.trim() || ''

function detectProvider(): OAuthProvider {
  if (AUTHKIT_DOMAIN) return 'workos'
  if (AUTH0_DOMAIN) return 'auth0'
  return null
}

function getIssuer(): string {
  const p = detectProvider()
  if (p === 'workos') return AUTHKIT_DOMAIN
  if (p === 'auth0') return `https://${AUTH0_DOMAIN}/`
  return ''
}

function getJwksUrl(): string {
  const p = detectProvider()
  if (p === 'workos') return `${AUTHKIT_DOMAIN}/oauth2/jwks`
  if (p === 'auth0') return `https://${AUTH0_DOMAIN}/.well-known/jwks.json`
  return ''
}

function getAudience(): string | undefined {
  const p = detectProvider()
  // AuthKit doesn't support RFC 8707 resource indicators yet.
  // Only verify audience if explicitly set via WORKOS_AUDIENCE.
  if (p === 'workos') return WORKOS_AUDIENCE || undefined
  if (p === 'auth0') return AUTH0_AUDIENCE || undefined
  return undefined
}

export function getAuthMode(): AuthMode {
  if (detectProvider()) return 'oauth'
  if (LEGACY_BEARER) return 'bearer'
  return 'none'
}

export function getProvider(): OAuthProvider {
  return detectProvider()
}

const jwksCache = (() => {
  const url = getJwksUrl()
  return url ? createRemoteJWKSet(new URL(url)) : null
})()

export type AuthContext = {
  subject: string
  scopes: Set<string>
  raw: JWTPayload
}

export function getAuthContext(res: Response): AuthContext | undefined {
  return (res.locals as { vaultAuth?: AuthContext }).vaultAuth
}

function extractBearer(req: Request): string {
  const header = req.header('authorization') || ''
  return header.toLowerCase().startsWith('bearer ') ? header.slice(7).trim() : ''
}

function unauthorized(res: Response, message: string, wwwAuth?: string): void {
  if (wwwAuth) {
    res.setHeader('WWW-Authenticate', wwwAuth)
  }
  res.status(401).json({
    jsonrpc: '2.0',
    error: { code: -32001, message },
    id: null,
  })
}

export async function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): Promise<void> {
  const mode = getAuthMode()

  if (mode === 'none') {
    next()
    return
  }

  const token = extractBearer(req)

  if (mode === 'bearer') {
    if (token === LEGACY_BEARER) {
      res.locals.vaultAuth = {
        subject: 'legacy-bearer',
        scopes: new Set([
          'vault:search',
          'vault:context:public',
          'vault:context:private',
          'vault:graph',
        ]),
        raw: {},
      } satisfies AuthContext
      next()
      return
    }
    unauthorized(res, 'invalid bearer token')
    return
  }

  // OAuth mode
  if (!token) {
    const wwwAuth = RESOURCE_URL
      ? `Bearer realm="mcp", resource_metadata="${RESOURCE_URL}/.well-known/oauth-protected-resource/mcp"`
      : 'Bearer realm="mcp"'
    unauthorized(res, 'missing bearer token', wwwAuth)
    return
  }

  if (!jwksCache) {
    unauthorized(res, 'auth not configured (issuer missing)')
    return
  }

  try {
    const verifyOptions: { issuer: string; audience?: string } = { issuer: getIssuer() }
    const aud = getAudience()
    if (aud) verifyOptions.audience = aud

    const { payload } = await jwtVerify(token, jwksCache, verifyOptions)

    const scopeClaim = typeof payload.scope === 'string' ? payload.scope : ''
    const permissions = Array.isArray(payload.permissions)
      ? (payload.permissions as string[])
      : []
    const scopes = new Set<string>([
      ...scopeClaim.split(/\s+/).filter(Boolean),
      ...permissions,
    ])

    res.locals.vaultAuth = {
      subject: typeof payload.sub === 'string' ? payload.sub : 'unknown',
      scopes,
      raw: payload,
    } satisfies AuthContext
    next()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    // Diagnostic dump — token shape only (no secret leak in normal hex), helps distinguish JWS / JWE / opaque
    const parts = token.split('.').length
    const head = token.slice(0, 16)
    const tail = token.slice(-8)
    const len = token.length
    console.error(`[auth] JWT verification failed: ${message} | token len=${len} parts=${parts} head=${head}... tail=...${tail}`)
    unauthorized(res, `invalid token: ${message}`)
  }
}

export function requireScope(scope: string) {
  return (_req: Request, res: Response, next: NextFunction): void => {
    const mode = getAuthMode()
    if (mode === 'none') {
      next()
      return
    }
    const ctx = getAuthContext(res)
    if (!ctx || !ctx.scopes.has(scope)) {
      res.status(403).json({
        jsonrpc: '2.0',
        error: { code: -32002, message: `scope required: ${scope}` },
        id: null,
      })
      return
    }
    next()
  }
}

export function hasScope(res: Response, scope: string): boolean {
  if (getAuthMode() === 'none') return true
  return Boolean(getAuthContext(res)?.scopes.has(scope))
}

export function buildProtectedResourceMetadata() {
  const provider = detectProvider()
  if (!RESOURCE_URL || !provider) {
    return null
  }

  const issuer = getIssuer()
  return {
    resource: `${RESOURCE_URL}/mcp`,
    authorization_servers: [issuer],
    bearer_methods_supported: ['header'],
    // Only expose scopes that the authorization server (WorkOS AuthKit) actually issues.
    // vault:* custom scopes are NOT registered with WorkOS — listing them here causes
    // ChatGPT to forward them to WorkOS authorize endpoint, triggering invalid_scope.
    scopes_supported: ['openid', 'profile', 'email', 'offline_access'],
    resource_documentation: `${RESOURCE_URL}/healthz`,
  }
}

export function buildAuthorizationServerMetadata() {
  const provider = detectProvider()
  if (!provider) return null

  if (provider === 'workos') {
    return {
      issuer: AUTHKIT_DOMAIN,
      authorization_endpoint: `${AUTHKIT_DOMAIN}/oauth2/authorize`,
      token_endpoint: `${AUTHKIT_DOMAIN}/oauth2/token`,
      registration_endpoint: `${AUTHKIT_DOMAIN}/oauth2/register`,
      jwks_uri: `${AUTHKIT_DOMAIN}/oauth2/jwks`,
      response_types_supported: ['code'],
      grant_types_supported: ['authorization_code', 'refresh_token'],
      token_endpoint_auth_methods_supported: ['none', 'client_secret_basic', 'client_secret_post'],
      code_challenge_methods_supported: ['S256'],
      scopes_supported: ['openid', 'profile', 'email', 'offline_access'],
    }
  }

  // auth0
  return {
    issuer: `https://${AUTH0_DOMAIN}/`,
    authorization_endpoint: `https://${AUTH0_DOMAIN}/authorize`,
    token_endpoint: `https://${AUTH0_DOMAIN}/oauth/token`,
    registration_endpoint: `https://${AUTH0_DOMAIN}/oidc/register`,
    jwks_uri: `https://${AUTH0_DOMAIN}/.well-known/jwks.json`,
    response_types_supported: ['code'],
    grant_types_supported: ['authorization_code', 'refresh_token'],
    token_endpoint_auth_methods_supported: ['none', 'client_secret_basic', 'client_secret_post'],
    code_challenge_methods_supported: ['S256'],
    scopes_supported: [
      'openid', 'profile', 'email', 'offline_access',
      'vault:search', 'vault:context:public', 'vault:context:private',
      'vault:graph', 'vault:admin',
    ],
  }
}
