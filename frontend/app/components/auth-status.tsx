"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { supabase } from "@/lib/supabase";

export function AuthStatus() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void supabase.auth.getUser().then(({ data }) => {
      if (active) {
        setEmail(data.user?.email ?? null);
        setLoading(false);
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user.email ?? null);
      setLoading(false);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  async function logout() {
    setLogoutError(null);
    const { error } = await supabase.auth.signOut();

    if (error) {
      setLogoutError(error.message);
      return;
    }

    router.refresh();
  }

  if (loading) {
    return <p className="text-sm text-zinc-500">Checking session…</p>;
  }

  if (!email) {
    return (
      <Link
        href="/login"
        className="text-sm text-green-400 hover:text-green-300"
      >
        Log in
      </Link>
    );
  }

  return (
    <div className="text-right">
      <p className="text-sm text-zinc-400">Signed in as {email}</p>
      <button
        type="button"
        onClick={logout}
        className="text-sm text-green-400 hover:text-green-300"
      >
        Log out
      </button>
      {logoutError && (
        <p role="alert" className="mt-1 text-sm text-red-400">
          {logoutError}
        </p>
      )}
    </div>
  );
}
