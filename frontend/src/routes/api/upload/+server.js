// src/routes/api/upload/+server.js
// This is our serverless function for handling file uploads.

import { json } from '@sveltejs/kit';
import { supabase } from '$lib/supabaseClient'; // Import our reusable Supabase client

/**
 * @param {{ request: Request }} param0
 */
export async function POST({ request }) {
  try {
    const formData = await request.formData();
    const file = formData.get('file');

    // This is a good, robust check
    if (!(file instanceof File)) {
      return json({ error: 'No file provided or invalid file type.' }, { status: 400 });
    }

    // FIXED: Added backticks (`) to create the template literal string
    const uniqueFileName = `${Date.now()}-${file.name}`;

    const { error: uploadError } = await supabase.storage
      .from('media_uploads')
      .upload(uniqueFileName, file);

    if (uploadError) {
      console.error('Supabase upload error:', uploadError);
      return json({ error: 'Failed to upload file to storage.' }, { status: 500 });
    }

    const { data: { publicUrl } } = supabase.storage
      .from('media_uploads')
      .getPublicUrl(uniqueFileName);

    return json({ url: publicUrl }, { status: 200 });

  } catch (err) {
    console.error('Server error:', err);
    return json({ error: 'An unexpected server error occurred.' }, { status: 500 });
  }
}