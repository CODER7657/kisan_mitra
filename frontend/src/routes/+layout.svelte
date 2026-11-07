<script lang="ts">
	// Fonts are self-hosted: only the weights and scripts the page uses.
	import '@fontsource/fraunces/latin-600.css';
	import '@fontsource/noto-sans/latin-400.css';
	import '@fontsource/noto-sans/latin-600.css';
	import '@fontsource/noto-sans-gujarati/gujarati-400.css';
	import '@fontsource/noto-sans-gujarati/gujarati-600.css';
	import '@fontsource/noto-sans-devanagari/devanagari-400.css';
	import '@fontsource/noto-sans-devanagari/devanagari-600.css';
	import '$lib/tokens.css';
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	// Fetch the two fonts every visitor sees first early, so text does not jump when they arrive.
	import frauncesHeading from '@fontsource/fraunces/files/fraunces-latin-600-normal.woff2?url';
	import notoBody from '@fontsource/noto-sans/files/noto-sans-latin-400-normal.woff2?url';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<link rel="preload" href={frauncesHeading} as="font" type="font/woff2" crossorigin="anonymous" />
	<link rel="preload" href={notoBody} as="font" type="font/woff2" crossorigin="anonymous" />
</svelte:head>

{@render children?.()}
