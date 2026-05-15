"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useEffect, useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
      }),
  );
  const [ready, setReady] = useState(process.env.NODE_ENV !== "development");

  useEffect(() => {
    if (process.env.NODE_ENV !== "development") return;
    import("@/mocks")
      .then(({ initMocks }) => initMocks())
      .catch(console.error)
      .finally(() => setReady(true));
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {ready ? children : null}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
