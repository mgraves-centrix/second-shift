/**
 * Every built surface, in the order a person meets them.
 *
 * Data rather than JSX, in its own module, for two reasons. The shell's tests
 * run under `node --test`, which strips types but does not transform JSX, so a
 * list living in `Shell.tsx` could only be asserted by reading the file's text —
 * and a test that greps source is a test that passes when the symbol it names
 * has been renamed.
 *
 * The second is that this is the extension point, and it has now been used
 * once: `app/morning/` was added as a single line here and appeared in the
 * desktop nav and in capture's footer without either shell being touched. A
 * test asserts every entry resolves to a route on disk, so a typo in the
 * extension point fails a run rather than a click.
 */
export interface Surface {
  readonly href: string;
  readonly label: string;
}

export const SURFACES: readonly Surface[] = [
  { href: "/", label: "Capture" },
  { href: "/morning/", label: "Morning" },
  { href: "/night/", label: "Night" },
];
