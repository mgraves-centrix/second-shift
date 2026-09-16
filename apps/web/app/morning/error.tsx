"use client";

import { RouteError } from "@/components/route-error/RouteError";

export default function MorningError(props: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError surface="The morning" {...props} />;
}
