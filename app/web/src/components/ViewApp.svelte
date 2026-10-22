<script lang="ts">
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';

  import Feed from './Feed.svelte';

  let { apiUrl }: { apiUrl: string } = $props();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false } },
  });
</script>

<QueryClientProvider client={queryClient}>
  <Feed {apiUrl} />
</QueryClientProvider>
