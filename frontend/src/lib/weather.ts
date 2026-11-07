// Turns one day of the rain forecast into a sky condition for the weather strip's icon.
// The backend sends daily rain totals and chances (Open-Meteo), not weather codes, so the
// condition is read from those two numbers. Kept here so it can be tested without a browser.

export type Sky = 'heavy-rain' | 'rain' | 'showers' | 'clear-day' | 'clear-night' | 'unknown';

export type ForecastDay = { date: string; rain_mm: number | null; rain_chance_pct: number | null };

/** Rain at or above this many mm in a day reads as heavy rain. */
export const HEAVY_RAIN_MM = 15;
/** Rain at or above this many mm, or this % chance, reads as a rainy day. */
export const RAIN_MM = 1;
export const RAIN_CHANCE_PCT = 60;
/** Any measurable rain, or this % chance, reads as a chance of showers. */
export const SHOWERS_CHANCE_PCT = 30;

const known = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n) && n >= 0;

/**
 * The sky for one forecast day. `night` only changes a clear sky (moon instead of sun).
 * A day with neither number usable is 'unknown', so the strip never shows a sunny icon
 * for a day it knows nothing about.
 */
export function skyFor(day: Partial<ForecastDay> | null | undefined, night = false): Sky {
	const mm = day?.rain_mm;
	const pct = day?.rain_chance_pct;
	if (!known(mm) && !known(pct)) return 'unknown';
	const rain = known(mm) ? mm : 0;
	const chance = known(pct) ? Math.min(pct, 100) : 0;
	if (rain >= HEAVY_RAIN_MM) return 'heavy-rain';
	if (rain >= RAIN_MM || chance >= RAIN_CHANCE_PCT) return 'rain';
	if (rain > 0 || chance >= SHOWERS_CHANCE_PCT) return 'showers';
	return night ? 'clear-night' : 'clear-day';
}

/** Screen-reader text for each sky; the icon itself is decorative. */
export const SKY_LABEL: Record<Sky, string> = {
	'heavy-rain': 'Heavy rain',
	rain: 'Rain',
	showers: 'Chance of showers',
	'clear-day': 'Clear',
	'clear-night': 'Clear night',
	unknown: 'Forecast unknown'
};

/** The local calendar date as YYYY-MM-DD, the format of the forecast's `date`. */
export function localDate(d: Date): string {
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Night is before 06:00 or from 19:00, local time. */
export function isNight(d: Date): boolean {
	const h = d.getHours();
	return h < 6 || h >= 19;
}

/** The sky to show for a forecast day: only today's entry can be a night sky. */
export function skyForDay(day: Partial<ForecastDay> | null | undefined, now: Date): Sky {
	return skyFor(day, day?.date === localDate(now) && isNight(now));
}
