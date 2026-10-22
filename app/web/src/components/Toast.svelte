<script lang="ts">
  import { glass } from '../lib/glass';

  let { text, kind, onClose }: { text: string; kind: 'outage' | 'done'; onClose?: () => void } = $props();
</script>

<div class="toast glass dim" data-kind={kind} role={kind === 'outage' ? 'alert' : 'status'} use:glass>
  <span>{text}</span>
  {#if onClose}<button class="close" type="button" aria-label="Đóng thông báo" onclick={onClose}>×</button>{/if}
</div>
