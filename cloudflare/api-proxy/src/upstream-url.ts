/**
 * Build an upstream URL that cannot escape the configured origin.
 *
 * `new URL("//evil/…", origin)` is protocol-relative and leaves the origin —
 * that is the SSRF Gemini flagged. Always assign pathname/search onto a URL
 * cloned from the trusted origin instead.
 */
export function buildUpstreamUrl(
  originBase: string,
  pathname: string,
  search: string,
): URL {
  const origin = new URL(originBase);
  const upstream = new URL(origin.href);

  // Collapse any leading slashes so "//evil" becomes "/evil" (same-origin path).
  const relativePath = pathname.replace(/^\/+/, "");
  const basePath = origin.pathname.replace(/\/+$/, "");
  upstream.pathname = `${basePath}/${relativePath}`.replace(/\/+/g, "/") || "/";
  upstream.search = search;

  if (upstream.origin !== origin.origin) {
    throw new Error(
      `upstream origin escaped configured origin: ${upstream.origin}`,
    );
  }

  return upstream;
}
