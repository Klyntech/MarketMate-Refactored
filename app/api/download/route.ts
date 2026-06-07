import { NextRequest, NextResponse } from "next/server"
import { readFile } from "fs/promises"
import { join } from "path"

const resources: Record<string, { path: string; filename: string; contentType: string }> = {
  "openapi": {
    path: "docs/openapi.json",
    filename: "marketmate-openapi.json",
    contentType: "application/json",
  },
  "event-schemas": {
    path: "docs/event-schemas.json",
    filename: "marketmate-event-schemas.json",
    contentType: "application/json",
  },
  "postman": {
    path: "docs/postman-collection.json",
    filename: "marketmate-postman.json",
    contentType: "application/json",
  },
  "insomnia": {
    path: "docs/insomnia-collection.json",
    filename: "marketmate-insomnia.json",
    contentType: "application/json",
  },
}

export async function GET(request: NextRequest) {
  const type = request.nextUrl.searchParams.get("type")

  if (!type || !resources[type]) {
    return NextResponse.json(
      {
        error: "Invalid resource type",
        message: `Valid types are: ${Object.keys(resources).join(", ")}`,
        available: Object.keys(resources),
      },
      { status: 400 }
    )
  }

  const resource = resources[type]
  const filePath = join(process.cwd(), "public", resource.path)

  try {
    const data = await readFile(filePath, "utf-8")

    // Validate it's valid JSON before serving
    JSON.parse(data)

    return new NextResponse(data, {
      headers: {
        "Content-Type": resource.contentType,
        "Content-Disposition": `attachment; filename="${resource.filename}"`,
        "Cache-Control": "public, max-age=3600",
        "Access-Control-Allow-Origin": "*",
      },
    })
  } catch (error) {
    // If file not found or invalid JSON
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json(
        { error: "Resource not found", message: `The requested resource '${type}' could not be found.` },
        { status: 404 }
      )
    }

    // JSON parse error or other
    return NextResponse.json(
      { error: "Resource error", message: "The requested resource could not be read." },
      { status: 500 }
    )
  }
}
