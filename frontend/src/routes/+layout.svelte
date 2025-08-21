<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	let { children } = $props();
</script>

<link href="{favicon}" rel="icon"/>
<slot />
