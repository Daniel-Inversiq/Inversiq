"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSessionContext } from "@/components/shared/session-provider";
import { getGoogleAuthStartUrl, register } from "@/lib/api/session";
import { ApiError } from "@/lib/api/client";
import { APP_ROUTES } from "@/lib/routes";

export default function RegisterPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useSessionContext();
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(APP_ROUTES.dashboard);
    }
  }, [isAuthenticated, isLoading, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Wachtwoord moet minimaal 8 tekens hebben.");
      return;
    }
    setSubmitting(true);
    try {
      await register({
        company_name: companyName || undefined,
        email,
        phone: phone || undefined,
        password,
      });
      router.replace(APP_ROUTES.dashboard);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError(err.message || "Er bestaat al een account met dit e-mailadres.");
        } else if (err.status === 0) {
          setError("De server is tijdelijk onbereikbaar. Probeer opnieuw.");
        } else {
          setError(err.message || "Registreren is mislukt.");
        }
      } else {
        setError("Registreren is mislukt.");
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
            <CardTitle className="text-2xl tracking-tight">Registreren</CardTitle>
            <CardDescription className="text-sm text-zinc-600 dark:text-zinc-400">
              Maak je account aan om klantaanvragen te ontvangen.
            </CardDescription>
            <p className="pt-1 text-xs text-zinc-500 dark:text-zinc-500">
              Je bent daarna direct klaar om offertes te sturen en klussen te beheren.
            </p>
          </CardHeader>
          <CardContent className="space-y-5 px-7 pb-7">
            {error ? (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            <Button
              type="button"
              variant="outline"
              className="h-11 w-full"
              onClick={() => {
                window.location.href = getGoogleAuthStartUrl(APP_ROUTES.dashboard);
              }}
            >
              Registreren met Google
            </Button>
            <div className="relative py-1 text-center text-xs text-zinc-500">
              <span className="absolute left-0 right-0 top-1/2 -z-10 h-px bg-zinc-200 dark:bg-zinc-800" />
              <span className="bg-white px-2 dark:bg-zinc-950">of</span>
            </div>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label
                  htmlFor="companyName"
                  className="text-sm font-medium text-zinc-700 dark:text-zinc-300"
                >
                  Bedrijfsnaam
                </Label>
                <Input
                  id="companyName"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                  className="h-11 border-zinc-300/90 bg-white focus-visible:ring-2 focus-visible:ring-primary/35 dark:border-zinc-700 dark:bg-zinc-950"
                />
              </div>
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
                <Label htmlFor="phone" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Telefoon
                </Label>
                <Input
                  id="phone"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  className="h-11 border-zinc-300/90 bg-white focus-visible:ring-2 focus-visible:ring-primary/35 dark:border-zinc-700 dark:bg-zinc-950"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
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
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Minimaal 8 tekens.</p>
              </div>
              <Button type="submit" disabled={submitting} className="h-11 w-full font-medium shadow-sm">
                {submitting ? (
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
                      aria-hidden="true"
                    />
                    Bezig met registreren...
                  </span>
                ) : (
                  "Registreren"
                )}
              </Button>
            </form>
            <p className="text-sm text-zinc-500">
              Heb je al een account?{" "}
              <Link href={APP_ROUTES.login} className="font-semibold text-primary hover:underline">
                Inloggen
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
