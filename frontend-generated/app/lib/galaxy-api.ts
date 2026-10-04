const apiBaseUrl =
  import.meta.env.VITE_GALAXY_RESOLVE_API_BASE_URL?.replace(/\/+$/, "") ?? "";

export function galaxyApiUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}
