<script lang="ts">
  import { glass } from '../lib/glass';
  import { badge, type Status } from '../lib/status';

  let { status }: { status: Status } = $props();
  const n = $derived(badge(status));
</script>

<span class="badge glass dim" data-color={n.color} role="status" aria-live="polite" use:glass><i aria-hidden="true"></i>{n.text}</span>
