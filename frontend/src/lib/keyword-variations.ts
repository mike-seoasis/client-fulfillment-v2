/**
 * Generates keyword variations from a primary keyword for highlighting.
 *
 * Splits the keyword into individual words, then generates common English
 * suffix variations (+s, +es, +ing, +er, +ers, and removals) for each word.
 * Returns a Set of lowercase variation strings, excluding the exact primary
 * keyword and its sub-phrases.
 */

const VOWELS = new Set(["a", "e", "i", "o", "u"]);

function addSuffixVariations(word: string): string[] {
  const variations: string[] = [];
  const len = word.length;

  if (len < 2) return variations;

  const lastChar = word[len - 1];
  const secondLast = word[len - 2];

  // --- Additions ---

  // +s (general plural)
  variations.push(word + "s");

  // +es (words ending in s, sh, ch, x, z, o)
  if (
    lastChar === "s" ||
    lastChar === "x" ||
    lastChar === "z" ||
    lastChar === "o" ||
    word.endsWith("sh") ||
    word.endsWith("ch")
  ) {
    variations.push(word + "es");
  }

  // +ing
  if (lastChar === "e" && secondLast !== "e") {
    // bake → baking (drop e, add ing)
    variations.push(word.slice(0, -1) + "ing");
  } else {
    variations.push(word + "ing");
  }

  // +er
  if (lastChar === "e") {
    variations.push(word + "r");
  } else {
    variations.push(word + "er");
  }

  // +ers
  if (lastChar === "e") {
    variations.push(word + "rs");
  } else {
    variations.push(word + "ers");
  }

  // consonant doubling for short words (run → running, runner)
  if (
    len >= 3 &&
    !VOWELS.has(lastChar) &&
    VOWELS.has(secondLast) &&
    !VOWELS.has(word[len - 3]) &&
    lastChar !== "w" &&
    lastChar !== "x" &&
    lastChar !== "y"
  ) {
    variations.push(word + lastChar + "ing");
    variations.push(word + lastChar + "er");
    variations.push(word + lastChar + "ers");
  }

  // --- Removals ---

  // -s
  if (lastChar === "s" && secondLast !== "s") {
    variations.push(word.slice(0, -1));
  }

  // -es
  if (word.endsWith("es") && len > 2) {
    variations.push(word.slice(0, -2));
  }

  // -ing → base form
  if (word.endsWith("ing") && len > 4) {
    const base = word.slice(0, -3);
    variations.push(base);
    // running → run (deduplicate trailing consonant)
    if (base.length >= 2 && base[base.length - 1] === base[base.length - 2]) {
      variations.push(base.slice(0, -1));
    }
    // baking → bake (restore trailing e)
    variations.push(base + "e");
  }

  // -er
  if (word.endsWith("er") && len > 3) {
    const base = word.slice(0, -2);
    variations.push(base);
    // runner → run
    if (base.length >= 2 && base[base.length - 1] === base[base.length - 2]) {
      variations.push(base.slice(0, -1));
    }
    variations.push(base + "e");
  }

  return variations;
}

export function generateVariations(keyword: string): Set<string> {
  const trimmed = keyword.trim().toLowerCase();
  if (!trimmed) return new Set();

  // Split into individual words, handling hyphens as word separators too
  const words = trimmed.split(/[\s-]+/).filter(Boolean);

  const variations = new Set<string>();

  for (const word of words) {
    // Add the word itself
    variations.add(word);

    // Add suffix variations
    for (const v of addSuffixVariations(word)) {
      variations.add(v);
    }
  }

  // Remove the exact primary keyword
  variations.delete(trimmed);

  // Remove sub-phrases (multi-word subsets of the original keyword)
  // e.g. for "best running shoes", remove "best running", "running shoes"
  if (words.length > 1) {
    for (let i = 0; i < words.length; i++) {
      for (let j = i + 2; j <= words.length; j++) {
        variations.delete(words.slice(i, j).join(" "));
      }
    }
  }

  return variations;
}
