<script lang="ts">
  import { type Post, imageUrl } from '../lib/api/client';
  import { glass } from '../lib/glass';
  import { formatTime } from '../lib/time';

  let {
    posts,
    id,
    apiUrl,
    fetchPost,
    onClose,
    onSwitch,
  }: {
    posts: Post[];
    id: string;
    apiUrl: string;
    fetchPost: (id: string) => Promise<Post | null>;
    onClose: () => void;
    onSwitch: (id: string) => void;
  } = $props();

  let dialog: HTMLDialogElement | undefined = $state();
  let fetchedPost = $state<Post | null>(null);
  let touchStartX = 0;
  const index = $derived(posts.findIndex((b) => b.id === id));
  const current = $derived(index >= 0 ? posts[index] : fetchedPost);
  const prev = $derived(index > 0 ? posts[index - 1] : undefined);
  const next = $derived(index >= 0 && index < posts.length - 1 ? posts[index + 1] : undefined);

  $effect(() => {
    if (dialog && !dialog.open) dialog.showModal();
  });

  $effect(() => {
    if (index < 0 && fetchedPost?.id !== id) fetchPost(id).then((b) => (fetchedPost = b));
  });

  $effect(() => {
    for (const b of [prev, next]) {
      if (b) new Image().src = imageUrl(apiUrl, b.id);
    }
  });

  function onKey(e: KeyboardEvent) {
    if (e.key === 'ArrowRight' && next) onSwitch(next.id);
    if (e.key === 'ArrowLeft' && prev) onSwitch(prev.id);
  }

  function onSwipe(e: TouchEvent) {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) < 50) return;
    const target = dx < 0 ? next : prev;
    if (target) onSwitch(target.id);
  }
</script>

<dialog
  bind:this={dialog}
  class="viewer"
  aria-labelledby="post-title"
  onclose={onClose}
  onkeydown={onKey}
  ontouchstart={(e) => (touchStartX = e.touches[0].clientX)}
  ontouchend={onSwipe}
>
  {#if current}
    <img src={imageUrl(apiUrl, current.id)} alt={current.title} width={current.width} height={current.height} />
    <div class="text">
      <h2 id="post-title">{current.title}</h2>
      {#if current.description}<p>{current.description}</p>{/if}
      <time datetime={current.created_at}>{formatTime(current.created_at)}</time>
    </div>
  {:else}
    <p role="status">Đang tải bài…</p>
  {/if}
  <button class="btn glass" type="button" onclick={() => dialog?.close()} use:glass>Quay lại</button>
</dialog>
