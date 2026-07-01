import { createClient } from "./supabase/client";

// Compatibility export for the existing client-only inventory page.
// New code should create the appropriate browser or server client explicitly.
export const supabase = createClient();
