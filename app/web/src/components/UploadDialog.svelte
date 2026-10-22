<script lang="ts">
  import { type Post, uploadPost, verifyCode } from '../lib/api/client';
  import { glass } from '../lib/glass';
  import { readCode, saveCode, forgetCode } from '../lib/storage';
  import { compressImage } from '../lib/compress-image';

  let { apiUrl, onDone, onClose }: { apiUrl: string; onDone: (b: Post) => void; onClose: () => void } = $props();

  let dialog: HTMLDialogElement | undefined = $state();
  let code = $state<string | null>(readCode());
  let codeInput = $state('');
  let file = $state<File | null>(null);
  let previewUrl = $state<string | null>(null);
  let title = $state('');
  let description = $state('');
  let progress = $state<number | null>(null);
  let error = $state<string | null>(null);
  let sending = $state(false);
  let idempotencyKey: string | null = null;

  $effect(() => {
    if (dialog && !dialog.open) dialog.showModal();
  });

  $effect(() => {
    const url = previewUrl;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  });

  async function submitCode(e: SubmitEvent) {
    e.preventDefault();
    error = null;
    const entered = codeInput.trim();
    const s = await verifyCode(apiUrl, entered);
    if (s === 204) {
      saveCode(entered);
      code = entered;
      codeInput = '';
    } else if (s === 429) {
      error = 'Thử sai quá nhiều lần. Đợi một lúc rồi thử lại.';
    } else if (s === 401) {
      error = 'Mã không đúng.';
    } else {
      error = 'Không kiểm tra được mã, thử lại sau.';
    }
  }

  function pick(f: File | null | undefined) {
    if (!f) return;
    if (!f.type.startsWith('image/')) {
      error = 'Hãy chọn một tệp ảnh.';
      return;
    }
    error = null;
    file = f;
    idempotencyKey = null;
    previewUrl = URL.createObjectURL(f);
  }

  function dropCode() {
    forgetCode();
    code = null;
  }

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (!file || !code) return;
    error = null;
    sending = true;
    progress = 0;
    idempotencyKey ??= crypto.randomUUID();
    try {
      const image = await compressImage(file);
      const result = await uploadPost(apiUrl, code, { idempotencyKey, title, description, image }, (p) => (progress = p));
      if (result.post) {
        idempotencyKey = null;
        onDone(result.post);
        dialog?.close();
        return;
      }
      if (result.status === 401) {
        dropCode();
        error = 'Mã đã bị đổi, nhập lại mã.';
      } else {
        error = result.error?.message ?? 'Không đăng được, thử lại.';
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Không xử lý được ảnh.';
    } finally {
      sending = false;
      progress = null;
    }
  }
</script>

<dialog bind:this={dialog} class="upload" aria-labelledby="upload-title" onclose={onClose}>
  <h2 id="upload-title">Đăng ảnh</h2>
  {#if !code}
    <form onsubmit={submitCode}>
      <label for="code-input">Mã bí mật của nhóm</label>
      <input id="code-input" type="password" autocomplete="current-password" bind:value={codeInput} required />
      <button class="btn glass tint" type="submit" use:glass>Tiếp tục</button>
    </form>
  {:else}
    <form onsubmit={submit}>
      <label
        class="dropzone"
        ondragover={(e) => e.preventDefault()}
        ondrop={(e) => {
          e.preventDefault();
          pick(e.dataTransfer?.files[0]);
        }}
      >
        {#if previewUrl}
          <img src={previewUrl} alt="Ảnh xem trước" />
        {:else}
          <span>Kéo ảnh vào đây hoặc bấm để chọn</span>
        {/if}
        <input type="file" accept="image/*" aria-label="Chọn ảnh" onchange={(e) => pick(e.currentTarget.files?.[0])} />
      </label>
      <label for="title-input">Tiêu đề <small>{title.length}/100</small></label>
      <input id="title-input" bind:value={title} maxlength="100" required />
      <label for="description-input">Mô tả <small>{description.length}/1000</small></label>
      <textarea id="description-input" bind:value={description} maxlength="1000" rows="3"></textarea>
      {#if progress !== null}<progress max="1" value={progress} aria-label="Tiến độ gửi"></progress>{/if}
      <div class="actions">
        <button class="btn glass" type="button" onclick={dropCode} use:glass>Quên mã</button>
        <button class="btn glass tint" type="submit" disabled={!file || sending} use:glass>{sending ? 'Đang gửi…' : 'Đăng'}</button>
      </div>
    </form>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  <button class="close" type="button" aria-label="Đóng" onclick={() => dialog?.close()}>×</button>
</dialog>
