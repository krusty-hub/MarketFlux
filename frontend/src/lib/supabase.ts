import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

let client: SupabaseClient | null = null;

if (supabaseUrl && supabaseAnonKey && !supabaseUrl.includes('your_supabase')) {
  try {
    client = createClient(supabaseUrl, supabaseAnonKey);
  } catch (err) {
    console.warn('Supabase client initialization warning:', err);
    client = null;
  }
}

export const supabase = client;

export const isSupabaseConfigured = (): boolean => {
  return Boolean(client);
};
