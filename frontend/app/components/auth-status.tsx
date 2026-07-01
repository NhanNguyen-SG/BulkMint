"use client";

import type { Session } from "@supabase/supabase-js";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { authenticatedApiFetch } from "@/lib/api/authenticated-fetch";
import { supabase } from "@/lib/supabase";

type BackendStatus =
  | { state: "logged-out" }
  | { state: "checking" }
  | { state: "verified"; userId: string }
  | { state: "error"; message: string };

export function AuthStatus() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({
    state: "logged-out",
  });

  useEffect(() => {
    let active = true;
    let verificationId = 0;

    async function verifyBackendSession() {
      const currentVerificationId = ++verificationId;
      setBackendStatus({ state: "checking" });

      try {
        const response = await authenticatedApiFetch("/me");
        const data: unknown = await response.json();

        if (!response.ok) {
          throw new Error(`Backend returned HTTP ${response.status}`);
        }

        if (
          typeof data !== "object" ||
          data === null ||
          !("user_id" in data) ||
          typeof data.user_id !== "string"
        ) {
          throw new Error("Backend returned an invalid /me response");
        }

        if (active && currentVerificationId === verificationId) {
          setBackendStatus({ state: "verified", userId: data.user_id });
        }
      } catch (error) {
        if (active && currentVerificationId === verificationId) {
          setBackendStatus({
            state: "error",
            message:
              error instanceof Error ? error.message : "Backend verification failed",
          });
        }
      }
    }

    function applySession(session: Session | null) {
      setEmail(session?.user.email ?? null);
      setLoading(false);

      if (!session) {
        verificationId += 1;
        setBackendStatus({ state: "logged-out" });
        return;
      }

      // Run after the auth callback returns; the fetch helper reads the current session.
      window.setTimeout(() => {
        if (active) {
          void verifyBackendSession();
        }
      }, 0);
    }

    void supabase.auth.getSession().then(({ data }) => {
      if (active) {
        applySession(data.session);
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      applySession(session);
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
      {backendStatus.state === "checking" && (
        <p className="text-xs text-zinc-500">Verifying backend session…</p>
      )}
      {backendStatus.state === "verified" && (
        <p className="text-xs text-green-400">
          Backend authenticated: {backendStatus.userId}
        </p>
      )}
      {backendStatus.state === "error" && (
        <p role="alert" className="text-xs text-red-400">
          Backend authentication failed: {backendStatus.message}
        </p>
      )}
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
