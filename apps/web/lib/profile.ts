/**
 * Is this deployment the judge instance?
 *
 * Read from the capability report the API already serves, never from a build
 * flag. `NEXT_PUBLIC_DEMO=1` would mean two builds, and constitution principle
 * 5 says one codebase separated only by compute profile — a build flag is
 * exactly the fork it exists to prevent.
 */
export function isDemoProfile(profile: string | null | undefined): boolean {
  return profile === "cloud";
}
