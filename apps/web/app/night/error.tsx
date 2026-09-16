"use client";

import { RouteError } from "@/components/route-error/RouteError";

export default function NightError(props: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError surface="The night view" {...props} />;
}
