import Link from "next/link";
import { routes } from "@/lib/routes";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-2 text-[22px] font-semibold text-ink">This page does not exist</h1>
      <Link href={routes.worklist} className="mt-4 text-[13px] text-accent hover:underline">
        Back to the worklist
      </Link>
    </div>
  );
}
