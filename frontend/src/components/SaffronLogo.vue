<template>
  <!-- The one saffron mark used everywhere: three stigmas over a crocus base. -->
  <span class="saffron-logo" :style="{ width: size + 'px', height: size + 'px' }" aria-hidden="true">
    <svg viewBox="0 0 32 32" :width="size" :height="size" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient :id="gradId" x1="4" y1="3" x2="28" y2="29" gradientUnits="userSpaceOnUse">
          <stop stop-color="#f4a93c" /><stop offset="1" stop-color="#d8661b" />
        </linearGradient>
      </defs>
      <path d="M16 16 C16 16 11 9 9 4 C13 6 15 11 16 16Z" :fill="fill" :opacity="variant === 'white' ? 0.95 : 1" />
      <path d="M16 16 C16 16 21 9 23 4 C19 6 17 11 16 16Z" :fill="fill" :opacity="variant === 'white' ? 0.95 : 1" />
      <path d="M16 16 C16 16 16 7 16 2 C17.6 6 17 11 16 16Z" :fill="fill" :opacity="variant === 'white' ? 0.95 : 1" />
      <path d="M16 15 C10 16 6 20 5 27 C12 27 15 22 16 16 C17 22 20 27 27 27 C26 20 22 16 16 15Z"
            :fill="fill" :opacity="variant === 'white' ? 1 : 0.92" />
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 28 },
  variant: { type: String, default: 'brand' },   // 'brand' | 'white'
})

// Two marks on one page must not share a gradient id, or the second one
const gradId = `saffron-grad-${Math.random().toString(36).slice(2, 8)}`
const fill = computed(() => (props.variant === 'white' ? '#fff' : `url(#${gradId})`))
</script>

<style scoped>
.saffron-logo { display: inline-grid; place-items: center; flex-shrink: 0; }
</style>
