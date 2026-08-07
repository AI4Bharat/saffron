# Update — Click-to-Edit Rendered LaTeX Across All Editable Tasks

**Date:** 2026-07-11
**Applies to:** Saffron Annotation Studio (`tts-saffron.ai4bharat.org`)
**Audience:** Annotators & the annotation-tooling team

---

## What changed (for annotators)

Every text box you **edit** now shows math **rendered** (nicely typeset, like a
textbook) instead of raw LaTeX code such as `\frac{1}{2}` or `$x^2$`.

- The field displays the **rendered** version by default — easy to read and proofread.
- **Click the box** and it instantly switches to the **raw text** so you can edit
  the underlying LaTeX / characters.
- **Click away (blur)** and it snaps back to the clean **rendered** view.

Nothing else about your workflow changes — Reset, the *Modified / Original* badge,
the character counter, RTL languages (Urdu/Arabic), and the keyboard shortcuts
(`Ctrl/⌘+Enter` submit, `Ctrl/⌘+S` save) all work exactly as before.

## Where it now works

This behaviour started in **Conversation (Editable)** tasks. It is now consistent
across **all** tasks where you edit text:

| Task type                       | Component                    | Editable fields upgraded                          |
|---------------------------------|------------------------------|---------------------------------------------------|
| Conversation (Editable)         | `ConversationEvaluation.vue` | pre-scene, each dialogue turn, post-scene *(existing)* |
| Sentence Correction             | `SentenceCorrection.vue`     | the correction / translation box                  |
| Translation Correction          | `TranslationCorrection.vue`  | pre-scene, each turn's translation, post-scene    |

Read-only reference text (e.g. the English source) was already shown rendered and
is unchanged.

## Why

Annotators were proofreading and editing raw LaTeX, which is hard to read and easy
to get wrong. Showing the rendered equation while reviewing — and only revealing
the raw markup on an explicit click — makes mistakes far easier to catch while
keeping full editing control.

---

## For developers

The pattern is a small, self-contained per-component addition (no new
dependencies — KaTeX is already loaded globally in `index.html`):

- **State:** `editingKey` ref; only one field edits at a time.
  Keys are `'text'` (Sentence), or `'pre_scene' | 'post_scene' | 'turn:<idx>'`
  (Translation / Conversation).
- **`startEdit(key)` / `stopEdit()`** toggle the key.
- **`v-focus` directive** focuses the textarea and moves the caret to the end when
  it mounts, so editing begins on the first click.
- **Template:** `<textarea v-if="editingKey === KEY" v-focus @blur="stopEdit">`
  else a `<div class="editable-rendered" @click="startEdit(KEY)">` containing
  `v-html="renderMath(value)"` (or a placeholder when empty). RTL is preserved by
  carrying `:class="{ 'rtl-text': isRtl }"` and `:dir` onto both views.
- **CSS:** `.editable-rendered` mirrors the `.correction-textarea` box so there is
  no layout jump when toggling.

### Deploy

Frontend is static (Caddy serves `frontend/dist`, `/api*` → gunicorn:4020):

```bash
cd /root/saffron/frontend && npm run build   # outputs to dist/, served immediately
```

Originals were backed up alongside each file as `*.vue.bak_<timestamp>` before the change.
