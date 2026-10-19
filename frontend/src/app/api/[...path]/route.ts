import { NextRequest, NextResponse } from 'next/server';

let _cachedWorkingBase: string | null = null;

function getCandidateBases(): string[] {
  const envUrls = [
    process.env.BACKEND_URL,
    process.env.NEXT_PUBLIC_BACKEND_URL,
  ]
    .filter((u): u is string => Boolean(u && u.trim()))
    .map(u => u.trim().replace(/\/$/, ''));

  const railwayInternalUrls = [
    'http://multimodal-video-forensics-fact.railway.internal:8080',
    'http://multimodal-video-forensics-fact.railway.internal:8000',
    'http://multimodal-video-forensics-fact:8080',
    'http://multimodal-video-forensics-fact:8000',
  ];

  const localUrls = [
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8080',
    'http://localhost:8000',
  ];

  const order = _cachedWorkingBase
    ? [_cachedWorkingBase, ...envUrls, ...railwayInternalUrls, ...localUrls]
    : [...envUrls, ...railwayInternalUrls, ...localUrls];

  return Array.from(new Set(order));
}

async function handleProxy(req: NextRequest, params: { path?: string[] }) {
  const pathSegments = params.path || [];
  const pathStr = pathSegments.join('/');
  const search = req.nextUrl.search || '';
  const candidates = getCandidateBases();

  const isBodyMethod = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method);
  const rawBody = isBodyMethod ? await req.arrayBuffer() : undefined;

  const reqHeaders = new Headers();
  req.headers.forEach((val, key) => {
    if (!['host', 'content-length'].includes(key.toLowerCase())) {
      reqHeaders.set(key, val);
    }
  });

  const triedErrors: Array<{ base: string; error: string }> = [];

  for (const base of candidates) {
    const targetUrl = `${base}/${pathStr}${search}`;
    try {
      const res = await fetch(targetUrl, {
        method: req.method,
        headers: reqHeaders,
        body: rawBody,
        cache: 'no-store',
      });

      // If we got an HTTP response from the backend (even 4xx/5xx from FastAPI), network connected!
      _cachedWorkingBase = base;

      const resBody = await res.arrayBuffer();
      const resHeaders = new Headers();
      res.headers.forEach((val, key) => {
        if (!['content-encoding', 'transfer-encoding'].includes(key.toLowerCase())) {
          resHeaders.set(key, val);
        }
      });

      return new NextResponse(resBody, {
        status: res.status,
        headers: resHeaders,
      });
    } catch (err: any) {
      triedErrors.push({ base, error: err.message || 'Connection failed' });
    }
  }

  return NextResponse.json(
    {
      error: 'Backend Proxy Error',
      message: 'Unable to connect to any backend candidate host',
      tried: triedErrors,
      path: pathStr,
    },
    { status: 502 }
  );
}

export async function GET(req: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const resolved = await context.params;
  return handleProxy(req, resolved);
}

export async function POST(req: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const resolved = await context.params;
  return handleProxy(req, resolved);
}

export async function PUT(req: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const resolved = await context.params;
  return handleProxy(req, resolved);
}

export async function DELETE(req: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const resolved = await context.params;
  return handleProxy(req, resolved);
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': '*',
    },
  });
}
