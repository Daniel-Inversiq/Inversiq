import { t } from "@/lib/i18n";

/** Short page title for the app utility bar (route-aware). */
export function shellPageTitle(pathname: string): string {
  const path = pathname || "/";

  /* Home with no dedicated shell title — avoids duplicate H1 when the app lands on `/`. */
  if (path === "/" || path === "") {
    return "";
  }

  if (path.startsWith("/dashboard")) {
    return "";
  }
  if (path.startsWith("/quotes")) {
    return t("nav.items.quotes");
  }
  if (path.startsWith("/jobs")) {
    return t("nav.items.jobs");
  }
  if (path.startsWith("/review")) {
    return t("nav.items.review");
  }
  if (path.startsWith("/agenda")) {
    return t("nav.items.agenda");
  }
  if (path.startsWith("/settings")) {
    return t("nav.items.settings");
  }
  if (path.startsWith("/billing")) {
    return t("billing.title");
  }
  if (path.startsWith("/customers")) {
    return t("customers.header.kicker");
  }
  if (path.startsWith("/uploads")) {
    return t("uploads.header.kicker");
  }
  if (path.startsWith("/workflows")) {
    return t("workflows.header.title");
  }
  if (path.startsWith("/handleiding")) {
    return t("shell.guide");
  }

  return t("nav.items.dashboard");
}
