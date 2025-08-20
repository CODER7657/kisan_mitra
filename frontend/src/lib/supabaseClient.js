// src/lib/supabaseClient.js
// This file creates and exports a single, reusable Supabase client instance.

import { createClient } from '@supabase/supabase-js';

// These lines read the secret keys you added to the Vercel dashboard.
// It's very important that the names here match the names in Vercel exactly.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// We create the Supabase client using our credentials.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);