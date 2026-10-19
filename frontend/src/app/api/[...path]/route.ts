import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  // 1. Explicit backend environment variables
  if (process.env.BACKEND_URL) {
    return process.env.BACKEND_URL.trim().replace(/\/$/, '');
  }
  if (process.env.NEXT_PUBLIC_BACKEND_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_URL.trim().replace(/\/$/, '');
  }
  // 2. Railway internal private network address
  if (process.env.RAILWAY_ENVIRONMENT) {
    return 'http://multimodal-video-forensics-fact.railway.internal:8000';
  }
  // 3. Localhost fallback for local development
  return 'http://127.0.0.1:8000';
}

async function handleProxy(req: NextRequest, params: { path?: string[] }) {
  const backendBase = getBackendUrl();
  const pathSegments = params.path || [];
  const pathStr = pathSegments.join('/');
  const search = req.nextUrl.search || '';
  const targetUrl = `${backendBase}/${pathStr}${search}`;

  try {
    const headers = new Headers();
    req.headers.forEach((val, key) => {
      // Don't forward host header to avoid SSL/SNI mismatch
      if (!['host', 'content-length'].includes(key.toLowerCase())) {
        headers.set(key, val);
      }
    });

    const isBodyMethod = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method);
    const body = isBodyMethod ? await req.arrayBuffer() : undefined;

    const res = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
      cache: 'no-store',
    });

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
    return NextResponse.json(
      {
        error: 'Backend Proxy Error',
        message: err.message,
        targetUrl,
        backendBase,
      },
      { status: 502 }
    );
  }
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
