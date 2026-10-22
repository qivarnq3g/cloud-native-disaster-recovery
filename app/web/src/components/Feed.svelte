<script lang="ts">
  import { createInfiniteQuery, type InfiniteData, useQueryClient } from '@tanstack/svelte-query';

  import { type Post, createApiClient, type PostPage } from '../lib/api/client';
  import { dismissNotice, step, pollInterval, newMachine, type HealthEvent } from '../lib/status';
  import PhotoGrid from './PhotoGrid.svelte';
  import TopBar from './TopBar.svelte';
  import Toast from './Toast.svelte';
  import PostViewer from './PostViewer.svelte';

  let { apiUrl }: { apiUrl: string } = $props();
  const api = createApiClient(apiUrl);
  const queryClient = useQueryClient();
  let machine = $state(newMachine());
  let uploadOpen = $state(false);
  let openPostId = $state<string | null>(null);

  const posts = createInfiniteQuery(() => ({
    queryKey: ['post'],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }): Promise<PostPage> => {
      const query = pageParam ? { limit: 24, before: pageParam } : { limit: 24 };
      const { data, error } = await api.GET('/v1/posts', { params: { query } });
      if (error || !data) throw new Error(error?.message ?? 'Không tải được danh sách.');
      return data;
    },
    getNextPageParam: (page: PostPage) => page.next ?? undefined,
  }));
  const allPosts = $derived(posts.data?.pages.flatMap((p) => p.posts) ?? []);

  async function fetchPost(id: string): Promise<Post | null> {
    const { data } = await api.GET('/v1/posts/{id}', { params: { path: { id } } });
    return data ?? null;
  }

  $effect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function check() {
      if (cancelled) return;
      if (document.hidden) {
        timer = setTimeout(check, 1000);
        return;
      }
      let event: HealthEvent;
      try {
        const r = await fetch(`${apiUrl}/healthz`, { signal: AbortSignal.timeout(3000), cache: 'no-store' });
        const v = await r.json();
        event = r.ok
          ? { kind: 'success', cluster: v.cluster, region: v.region, readOnly: v.read_only, at: Date.now() }
          : { kind: 'failure', at: Date.now() };
      } catch {
        event = { kind: 'failure', at: Date.now() };
      }
      if (cancelled) return;
      const previousKind = machine.status.kind;
      machine = step(machine, event);
      if (previousKind === 'outage' && machine.status.kind === 'up') queryClient.invalidateQueries({ queryKey: ['post'] });
      timer = setTimeout(check, pollInterval(machine));
    }
    check();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  });

  $effect(() => {
    if (!machine.notice) return;
    const h = setTimeout(() => (machine = dismissNotice(machine)), 10_000);
    return () => clearTimeout(h);
  });

  $effect(() => {
    const syncFromUrl = () => (openPostId = new URLSearchParams(location.search).get('post'));
    syncFromUrl();
    addEventListener('popstate', syncFromUrl);
    return () => removeEventListener('popstate', syncFromUrl);
  });

  function openPost(id: string) {
    history.pushState({ post: id }, '', `?post=${id}`);
    openPostId = id;
  }

  function switchPost(id: string) {
    history.replaceState(history.state, '', `?post=${id}`);
    openPostId = id;
  }

  function close() {
    if (!openPostId) return;
    openPostId = null;
    if (history.state?.post) history.back();
    else history.replaceState(null, '', location.pathname);
  }

  function prepend(b: Post) {
    queryClient.setQueryData<InfiniteData<PostPage>>(['post'], (old) =>
      old
        ? { ...old, pages: [{ ...old.pages[0], posts: [b, ...old.pages[0].posts.filter((x) => x.id !== b.id)] }, ...old.pages.slice(1)] }
        : old,
    );
  }
</script>

<TopBar status={machine.status} onUpload={() => (uploadOpen = true)} />

<main>
  <h1>Ảnh của nhóm</h1>
  <p class="subtitle">Mỗi ảnh được cất ở kho chính và chép sang Nhật Bản.</p>
  {#if posts.isPending && machine.status.kind !== 'outage'}
    <p class="empty-state" role="status">Đang tải ảnh…</p>
  {:else if posts.isError && allPosts.length === 0}
    <p class="empty-state" role="status">Chưa tải được ảnh. Trang sẽ tự tải lại khi máy chủ chạy lại.</p>
  {:else if posts.isSuccess && allPosts.length === 0}
    <p class="empty-state">Chưa có ảnh nào.</p>
  {/if}
  <PhotoGrid
    posts={allPosts}
    {apiUrl}
    hasMore={posts.hasNextPage}
    loadingMore={posts.isFetchingNextPage}
    loadMore={() => posts.fetchNextPage()}
    onOpen={openPost}
  />
</main>

{#if openPostId}
  <PostViewer posts={allPosts} id={openPostId} {apiUrl} {fetchPost} onClose={close} onSwitch={switchPost} />
{/if}

{#if uploadOpen}
  <Toast text="Đăng ảnh sắp có." kind="done" onClose={() => (uploadOpen = false)} />
{/if}

{#if machine.status.kind === 'outage'}
  <Toast text="Máy chủ đang được khôi phục. Ảnh đã tải vẫn xem được; trang tự thử lại." kind="outage" />
{:else if machine.notice}
  <Toast text={machine.notice} kind="done" onClose={() => (machine = dismissNotice(machine))} />
{/if}
