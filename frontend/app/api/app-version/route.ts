import release from "@/app/release.json";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(
    { revision: release.revision },
    {
      headers: {
        "Cache-Control": "private, no-store, max-age=0, must-revalidate",
        Pragma: "no-cache",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}
