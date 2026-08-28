// ULID generation, matching the server's implementation.
//
// The client owns identity. The identifier is generated at the moment of
// capture and embeds that instant, and the server refuses one whose embedded
// timestamp disagrees with the capture instant sent alongside it — because
// ordering by (created_at_ms, id) would otherwise sort by two different clocks.

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // Crockford base32

function encode(value: number, length: number): string {
  let out = "";
  for (let i = 0; i < length; i += 1) {
    out = ALPHABET[value % 32] + out;
    value = Math.floor(value / 32);
  }
  return out;
}

/** A 26-character ULID: 48 bits of timestamp, 80 bits of randomness. */
export function newUlid(nowMs: number): string {
  const random = new Uint8Array(10);
  crypto.getRandomValues(random);
  let randomPart = "";
  // 80 bits in two 40-bit halves: a single Number cannot hold 80 bits exactly.
  const high = random.slice(0, 5).reduce((acc, b) => acc * 256 + b, 0);
  const low = random.slice(5, 10).reduce((acc, b) => acc * 256 + b, 0);
  randomPart = encode(high, 8) + encode(low, 8);
  return encode(nowMs, 10) + randomPart;
}
