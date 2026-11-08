// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}

	// Read in +page.svelte; required when building for production (see vite.config.ts).
	interface ImportMetaEnv {
		readonly VITE_API_URL?: string;
	}
}

export {};
