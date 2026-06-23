import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export async function POST(request: NextRequest) {
    let body: { username?: string; password?: string }
    try {
        body = (await request.json()) as { username?: string; password?: string }
    } catch {
        return NextResponse.json({ error: "Invalid request" }, { status: 400 })
    }

    const validUser = process.env.AUTH_USERNAME ?? "admin"
    const validPass = process.env.AUTH_PASSWORD ?? ""
    const secret = process.env.AUTH_SECRET ?? ""

    if (!secret || body.username !== validUser || body.password !== validPass) {
        return NextResponse.json({ error: "Invalid credentials" }, { status: 401 })
    }

    const response = NextResponse.json({ ok: true })
    response.cookies.set("cam_auth", secret, {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 30,
    })
    return response
}

export async function DELETE() {
    const response = NextResponse.json({ ok: true })
    response.cookies.set("cam_auth", "", {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        maxAge: 0,
    })
    return response
}
