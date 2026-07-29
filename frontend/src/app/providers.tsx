import { useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { TooltipProvider } from '@/components/ui/primitives'
import { ApiError } from '@/services/apiClient'

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: (failureCount, error) => {
              // A 4xx will not fix itself; retrying only delays the error the
              // user needs to see.
              if (error instanceof ApiError && error.status && error.status < 500) return false
              return failureCount < 2
            },
            refetchOnWindowFocus: false,
          },
          mutations: { retry: false },
        },
      }),
  )

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  )
}
