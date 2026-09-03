/**
 * Every built surface, in the order a person meets them.
 *
 * Data rather than JSX, in its own module, for two reasons. The shell's tests
 * run under `node --test`, which strips types but does not transform JSX, so a
 * list living in `Shell.tsx` could only be asserted by reading the file's text —
 * and a test that greps source is a test that passes when the symbol it names
 * has been renamed.
 *
 * The second is that this is the extension point: adding `app/morning/` is one
 * line here, and it appears in the desktop nav and the capture footer at once.
 */
export interface Surface {
  readonly href: string;
  readonly label: string;
}

export const SURFACES: readonly Surface[] = [
  { href: "/", label: "Capture" },
  { href: "/night/", label: "Night" },
];
