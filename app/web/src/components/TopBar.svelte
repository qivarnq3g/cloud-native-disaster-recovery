<script lang="ts">
  import { glass } from '../lib/glass';
  import type { Status } from '../lib/status';
  import StatusBadge from './StatusBadge.svelte';

  let { status, onUpload }: { status: Status; onUpload: () => void } = $props();
  const canUpload = $derived(!(status.kind === 'up' && status.readOnly));
</script>

<header class="bar glass" use:glass>
  <a class="name" href="/?intro">DR · Nhóm 23</a>
  <StatusBadge {status} />
  <nav class="right" aria-label="Điều hướng">
    <a class="link" href="/?intro">Giới thiệu</a>
    {#if canUpload}
      <button class="btn glass tint small" type="button" onclick={onUpload} use:glass>Đăng ảnh</button>
    {/if}
  </nav>
</header>
