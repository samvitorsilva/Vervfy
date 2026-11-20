import { cookies } from "next/headers";
import PageLoading from "@/components/page-loading";

export default async function LoadingPage() {
  const cookieStore = await cookies();
  return <PageLoading signedInHint={Boolean(cookieStore.get("auralis_session")?.value)} />;
}
