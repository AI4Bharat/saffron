<template>
  <span class="diff-toggle" :class="{ off: !on, inherited: !overridden && inherit }">
    <button type="button" class="dt-switch" :disabled="disabled" :title="titleText"
            @click.stop="$emit('toggle', !on)">
      <span class="dt-track"><span class="dt-knob"></span></span>
      <span class="dt-label">{{ on ? 'On' : 'Off' }}</span>
    </button>
    <span v-if="inherit && !overridden" class="dt-auto"
          :title="`No override here — follows the ${inherit}.`">auto</span>
    <button v-else-if="inherit && overridden" type="button" class="dt-clear"
            :title="`Set here. Click to remove the override and follow the ${inherit} again.`"
            @click.stop="$emit('clear')">
      <i class="bi bi-x-circle-fill"></i>
    </button>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  on: { type: Boolean, required: true },          // the RESOLVED value shown by the switch
  overridden: { type: Boolean, default: false },  // true when this level has its own stored value
  inherit: { type: String, default: '' },         // the level above, e.g. 'language setting'; '' = root level
  disabled: { type: Boolean, default: false },
})

defineEmits(['toggle', 'clear'])

const titleText = computed(() => {
  const state = props.on
    ? 'ON — annotators label difficulty here'
    : 'OFF — the difficulty step is hidden here'
  if (!props.inherit) return `${state}. Click to flip.`
  return props.overridden
    ? `${state} (set at this level). Click to flip.`
    : `${state} (follows the ${props.inherit}). Click to set it here.`
})
</script>

<style scoped>
.diff-toggle { display: inline-flex; align-items: center; gap: .35rem; vertical-align: middle; }
.dt-switch { display: inline-flex; align-items: center; gap: .4rem; border: none; background: none;
             padding: .15rem 0; cursor: pointer; }
.dt-switch:disabled { opacity: .5; cursor: not-allowed; }
.dt-track { width: 32px; height: 18px; border-radius: 999px; background: #198754; position: relative;
            flex-shrink: 0; display: inline-block; transition: background .18s ease, opacity .18s ease; }
.diff-toggle.off .dt-track { background: #ced4da; }
.diff-toggle.inherited .dt-track { opacity: .5; }
.dt-knob { position: absolute; top: 2px; left: 16px; width: 14px; height: 14px; border-radius: 50%;
           background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.3); transition: left .18s ease; }
.diff-toggle.off .dt-knob { left: 2px; }
.dt-label { font-size: .72rem; font-weight: 700; color: #198754; min-width: 20px; text-align: left; }
.diff-toggle.off .dt-label { color: #6c757d; }
.dt-auto { font-size: .58rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
           color: #adb5bd; border: 1px dashed #ced4da; border-radius: 999px; padding: .05rem .35rem;
           cursor: help; user-select: none; }
.dt-clear { border: none; background: none; padding: 0; color: #d8661b; font-size: .85rem;
            line-height: 1; cursor: pointer; opacity: .65; transition: opacity .15s ease; }
.dt-clear:hover { opacity: 1; }
</style>
