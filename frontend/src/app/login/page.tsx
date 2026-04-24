"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSessionContext } from "@/components/shared/session-provider";
import { getGoogleAuthStartUrl, login } from "@/lib/api/session";
import { ApiError } from "@/lib/api/client";
import { APP_ROUTES } from "@/lib/routes";

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginLoading />}>
      <LoginContent />
    </Suspense>
  );
}

function LoginLoading() {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(1000px_500px_at_50%_-10%,rgba(2,6,23,0.06),transparent)] dark:bg-[radial-gradient(1000px_500px_at_50%_-10%,rgba(255,255,255,0.05),transparent)]"
      />
      <div className="relative w-full max-w-[460px]">
        <p className="mb-4 text-center text-sm font-medium tracking-tight text-zinc-600 dark:text-zinc-400">
          Inversiq
        </p>
        <Card className="w-full rounded-2xl border-zinc-200/80 shadow-sm dark:border-zinc-800">
          <CardHeader className="space-y-2 px-7 pb-2 pt-7">
            <CardTitle className="text-2xl tracking-tight">Inloggen</CardTitle>
            <CardDescription className="text-sm text-zinc-600 dark:text-zinc-400">
              Gebruik je account om verder te gaan.
            </CardDescription>
          </CardHeader>
          <CardContent className="px-7 pb-7 pt-2">
            <div className="h-24 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useSessionContext();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const registerSuccess = searchParams.get("registered") === "1";
  const nextPath = useMemo(() => searchParams.get("next") || APP_ROUTES.dashboard, [searchParams]);
  const oauthErrorCode = searchParams.get("oauth_error");
  const oauthErrorMessage = useMemo(() => {
    if (!oauthErrorCode) {
      return null;
    }
    const messageByCode: Record<string, string> = {
      google_cancelled: "Google-inloggen is geannuleerd. Probeer het opnieuw.",
      google_invalid_state: "De inlogsessie is verlopen. Start Google-inloggen opnieuw.",
      google_email_missing: "Google gaf geen e-mailadres terug. Gebruik e-mail/wachtwoord.",
      google_account_inactive: "Dit account is gedeactiveerd. Neem contact op met support.",
      google_not_configured: "Google-inloggen is tijdelijk niet beschikbaar.",
      google_callback_error: "Google-inloggen is mislukt. Probeer het zo opnieuw.",
    };
    return messageByCode[oauthErrorCode] ?? "Google-inloggen is mislukt. Probeer het zo opnieuw.";
  }, [oauthErrorCode]);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(APP_ROUTES.dashboard);
    }
  }, [isAuthenticated, isLoading, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password, next: nextPath });
      router.replace(nextPath);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("Ongeldige e-mail of wachtwoord.");
        } else if (err.status === 0) {
          setError("Inloggen lukt nu niet. Probeer het zo opnieuw.");
        } else {
          setError("Inloggen lukt nu niet. Probeer het zo opnieuw.");
        }
      } else {
        setError("Inloggen lukt nu niet. Probeer het zo opnieuw.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(1000px_500px_at_50%_-10%,rgba(2,6,23,0.06),transparent)] dark:bg-[radial-gradient(1000px_500px_at_50%_-10%,rgba(255,255,255,0.05),transparent)]"
      />
      <div className="relative w-full max-w-[460px]">
        <p className="mb-4 text-center text-sm font-medium tracking-tight text-zinc-600 dark:text-zinc-400">
          Inversiq
        </p>
        <Card className="w-full rounded-2xl border-zinc-200/80 shadow-sm dark:border-zinc-800">
          <CardHeader className="space-y-2 px-7 pb-2 pt-7">
            <CardTitle className="text-2xl tracking-tight">Inloggen</CardTitle>
            <CardDescription className="text-sm text-zinc-600 dark:text-zinc-400">
              Gebruik je account om verder te gaan.
            </CardDescription>
            <p className="pt-1 text-xs text-zinc-500 dark:text-zinc-500">
              Veilig inloggen in je Inversiq account
            </p>
          </CardHeader>
          <CardContent className="space-y-5 px-7 pb-7">
            {registerSuccess ? (
              <Alert>
                <AlertDescription>Account aangemaakt. Je kunt nu inloggen.</AlertDescription>
              </Alert>
            ) : null}
            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {oauthErrorMessage ? (
              <Alert variant="destructive">
                <AlertDescription>{oauthErrorMessage}</AlertDescription>
              </Alert>
            ) : null}
            <Button
              type="button"
              variant="outline"
              className="h-11 w-full"
              onClick={() => {
                window.location.href = getGoogleAuthStartUrl(nextPath);
              }}
            >
              Inloggen met Google
            </Button>
            <div className="relative py-1 text-center text-xs text-zinc-500">
              <span className="absolute left-0 right-0 top-1/2 -z-10 h-px bg-zinc-200 dark:bg-zinc-800" />
              <span className="bg-white px-2 dark:bg-zinc-950">of</span>
            </div>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  E-mail
                </Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="h-11 border-zinc-300/90 bg-white focus-visible:ring-2 focus-visible:ring-primary/35 dark:border-zinc-700 dark:bg-zinc-950"
                />
              </div>
              <div className="space-y-2">
                <Label
                  htmlFor="password"
                  className="text-sm font-medium text-zinc-700 dark:text-zinc-300"
                >
                  Wachtwoord
                </Label>
                <Input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-11 border-zinc-300/90 bg-white focus-visible:ring-2 focus-visible:ring-primary/35 dark:border-zinc-700 dark:bg-zinc-950"
                />
              </div>
              <Button type="submit" disabled={submitting} className="h-11 w-full font-medium shadow-sm">
                {submitting ? (
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
                      aria-hidden="true"
                    />
                    Bezig met inloggen...
                  </span>
                ) : (
                  "Inloggen"
                )}
              </Button>
            </form>
            <p className="text-sm text-zinc-500">
              Nog geen account?{" "}
              <Link href={APP_ROUTES.register} className="font-semibold text-primary hover:underline">
                Registreren
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
