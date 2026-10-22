<script lang="ts">
  import { type Post, thumbnailUrl } from '../lib/api/client';
  import { targetHeight, layoutGrid } from '../lib/grid';

  const CAPTION = 24;
  let {
    posts,
    apiUrl,
    hasMore,
    loadingMore,
    loadMore,
    onOpen,
  }: { posts: Post[]; apiUrl: string; hasMore: boolean; loadingMore: boolean; loadMore: () => void; onOpen: (id: string) => void } = $props();

  let containerWidth = $state(0);
  let sentinel: HTMLDivElement | undefined = $state();
  const byId = $derived(new Map(posts.map((b) => [b.id, b])));
  const grid = $derived(
    containerWidth > 0 ? layoutGrid(posts.map((b) => ({ id: b.id, width: b.width, height: b.height })), containerWidth, targetHeight(containerWidth), 8, CAPTION) : { tiles: [], totalHeight: 0 },
  );

  $effect(() => {
    if (!sentinel) return;
    const io = new IntersectionObserver((e) => {
      if (e[0]?.isIntersecting && hasMore && !loadingMore) loadMore();
    }, { rootMargin: '800px' });
    io.observe(sentinel);
    return () => io.disconnect();
  });
</script>

<div class="grid" bind:clientWidth={containerWidth} style:height="{grid.totalHeight}px">
  {#each grid.tiles as tile (tile.id)}
    {@const b = byId.get(tile.id)}
    {#if b}
      <button
        class="tile"
        type="button"
        style:left="{tile.x}px"
        style:top="{tile.y}px"
        style:width="{tile.width}px"
        style:height="{tile.height + CAPTION}px"
        aria-label={b.title}
        onclick={() => onOpen(tile.id)}
      >
        <img src={thumbnailUrl(apiUrl, tile.id)} alt={b.title} loading="lazy" decoding="async" width={Math.round(tile.width)} height={Math.round(tile.height)} style:height="{tile.height}px" />
        <span class="caption" aria-hidden="true">{b.title}</span>
      </button>
    {/if}
  {/each}
</div>
<div bind:this={sentinel} aria-hidden="true"></div>
{#if loadingMore}<p class="empty-state" role="status">Đang tải thêm…</p>{/if}
