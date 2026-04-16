/**
 * preflightChecker.js
 *
 * Runs 6 quality checks on every post before it is sent to the Taplio API.
 * Called after client approval — this is the final gate before a post goes live.
 *
 * Used in: n8n Function node — Step 14 (between approval webhook and Taplio scheduling)
 * Runtime: Node.js (n8n built-in)
 */

// ─── Configuration ────────────────────────────────────────────────────────────
// These can be overridden by passing options to runPreflightChecks()

const DEFAULT_CONFIG = {
  minLength: 50,
  maxLength: 3000,
  duplicateWindowDays: 60,
  // Add/remove terms as needed. Keep lowercase — comparison is case-insensitive.
  profanityList: [
    'fuck', 'shit', 'asshole', 'bastard', 'bitch', 'cunt', 'dick',
    'piss', 'damn', 'crap',
  ],
};

// ─── Individual Checks ────────────────────────────────────────────────────────

/**
 * CHECK 1: Placeholder detection
 * Blocks posts that contain unfilled template placeholders.
 */
function checkPlaceholders(text) {
  const pattern = /\[NAME\]|\[DATE\]|\[INSERT\]|\[CLIENT\]|\[COMPANY\]|\{\{[^}]+\}\}/gi;
  const matches = text.match(pattern);
  if (matches) {
    return {
      passed: false,
      code: 'PLACEHOLDER_DETECTED',
      severity: 'BLOCK',
      message: `Post contains unfilled placeholder(s): ${[...new Set(matches)].join(', ')}`,
    };
  }
  return { passed: true };
}

/**
 * CHECK 2: Character count
 * Blocks posts that exceed LinkedIn's 3,000-character limit or are too short.
 */
function checkCharacterCount(text, config = DEFAULT_CONFIG) {
  if (text.length < config.minLength) {
    return {
      passed: false,
      code: 'POST_TOO_SHORT',
      severity: 'BLOCK',
      message: `Post is ${text.length} characters — minimum is ${config.minLength}.`,
    };
  }
  if (text.length > config.maxLength) {
    return {
      passed: false,
      code: 'POST_TOO_LONG',
      severity: 'BLOCK',
      message: `Post is ${text.length} characters — LinkedIn maximum is ${config.maxLength}.`,
    };
  }
  return { passed: true };
}

/**
 * CHECK 3: Profanity / sensitive terms
 * Blocks posts that contain terms from the profanity list.
 * Uses word-boundary matching to avoid false positives (e.g. "classic" contains "ass").
 */
function checkProfanity(text, config = DEFAULT_CONFIG) {
  const lowerText = text.toLowerCase();
  const found = config.profanityList.filter((term) => {
    const regex = new RegExp(`\\b${term}\\b`, 'i');
    return regex.test(lowerText);
  });
  if (found.length > 0) {
    return {
      passed: false,
      code: 'PROFANITY_DETECTED',
      severity: 'BLOCK',
      message: `Post contains flagged term(s): ${found.join(', ')}. Review before publishing.`,
    };
  }
  return { passed: true };
}

/**
 * CHECK 4: Empty post
 * Belt-and-suspenders — catches edge cases the validator may have missed.
 */
function checkNotEmpty(text) {
  if (!text || text.trim().length === 0) {
    return {
      passed: false,
      code: 'EMPTY_POST',
      severity: 'BLOCK',
      message: 'Post text is empty.',
    };
  }
  return { passed: true };
}

/**
 * CHECK 5: Duplicate detection
 * Flags posts that are identical (or near-identical) to posts published in the
 * last N days. Uses simple hash comparison — pass recentPostHashes as an array
 * of { hash: string, publishedAt: Date, postId: string } objects.
 *
 * @param {string} text
 * @param {Array<{hash: string, publishedAt: string, postId: string}>} recentPostHashes
 * @param {object} config
 */
function checkDuplicate(text, recentPostHashes = [], config = DEFAULT_CONFIG) {
  const hash = simpleHash(text.trim().toLowerCase());
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - config.duplicateWindowDays);

  const duplicate = recentPostHashes.find((entry) => {
    const publishedAt = new Date(entry.publishedAt);
    return entry.hash === hash && publishedAt >= cutoff;
  });

  if (duplicate) {
    return {
      passed: false,
      code: 'DUPLICATE_POST',
      severity: 'BLOCK',
      message: `Post is identical to one published on ${duplicate.publishedAt} (ID: ${duplicate.postId}).`,
    };
  }
  return { passed: true, hash };
}

/**
 * CHECK 6: Named entity detection
 * FLAGS (does not block) posts containing a full name that is not the client's name.
 * Uses a simple heuristic: two adjacent capitalised words that look like a name.
 * Sends a review request to the operator — does not stop the batch.
 *
 * @param {string} text
 * @param {string} clientName - e.g. "Jane Smith"
 */
function checkNamedEntities(text, clientName = '') {
  // Match "Firstname Lastname" patterns — two capitalised words
  const namePattern = /\b([A-Z][a-z]{1,})\s([A-Z][a-z]{1,})\b/g;
  const matches = [...text.matchAll(namePattern)].map((m) => m[0]);

  // Remove the client's own name from matches
  const clientNameNormalised = clientName.trim().toLowerCase();
  const externalNames = matches.filter(
    (name) => name.toLowerCase() !== clientNameNormalised
  );

  // Remove common false positives (LinkedIn, Monday, etc.)
  const falsePositives = new Set([
    'LinkedIn', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
    'Saturday', 'Sunday', 'January', 'February', 'March', 'April', 'May',
    'June', 'July', 'August', 'September', 'October', 'November', 'December',
    'United States', 'United Kingdom', 'New York', 'San Francisco',
    'North America', 'South America',
  ]);

  const flagged = [...new Set(externalNames)].filter((name) => !falsePositives.has(name));

  if (flagged.length > 0) {
    return {
      passed: true, // FLAG only — does not block
      code: 'NAMED_ENTITY_DETECTED',
      severity: 'FLAG',
      message: `Post may reference a third party: ${flagged.join(', ')}. ` +
        'Confirm this is intentional and does not create defamation exposure before publishing.',
      flaggedNames: flagged,
    };
  }
  return { passed: true };
}

// ─── Utility ──────────────────────────────────────────────────────────────────

/**
 * Deterministic string hash (djb2 algorithm).
 * Used for duplicate detection — not cryptographic.
 */
function simpleHash(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return (hash >>> 0).toString(16);
}

// ─── Main Entry Point ─────────────────────────────────────────────────────────

/**
 * Run all preflight checks on a single post.
 *
 * @param {object} params
 * @param {string}  params.text               - Post body text
 * @param {string}  params.clientName         - Client's full name (for named entity check)
 * @param {Array}   params.recentPostHashes   - Array of recent post hashes from Airtable
 * @param {object}  [params.config]           - Optional config overrides
 *
 * @returns {{
 *   postText: string,
 *   action: 'PUBLISH' | 'BLOCK' | 'FLAG_AND_PUBLISH',
 *   checks: Array<{check: string, passed: boolean, severity?: string, code?: string, message?: string}>,
 *   blockedReasons: string[],
 *   flaggedReasons: string[],
 *   hash: string
 * }}
 */
function runPreflightChecks({ text, clientName = '', recentPostHashes = [], config = DEFAULT_CONFIG }) {
  const results = [];

  // Run all checks
  const emptyCheck    = checkNotEmpty(text);
  const lengthCheck   = checkCharacterCount(text, config);
  const placeholderCheck = checkPlaceholders(text);
  const profanityCheck   = checkProfanity(text, config);
  const duplicateCheck   = checkDuplicate(text, recentPostHashes, config);
  const entityCheck      = checkNamedEntities(text, clientName);

  results.push({ check: 'NOT_EMPTY',       ...emptyCheck });
  results.push({ check: 'CHARACTER_COUNT', ...lengthCheck });
  results.push({ check: 'PLACEHOLDERS',   ...placeholderCheck });
  results.push({ check: 'PROFANITY',      ...profanityCheck });
  results.push({ check: 'DUPLICATE',      ...duplicateCheck });
  results.push({ check: 'NAMED_ENTITY',   ...entityCheck });

  const blocked = results.filter((r) => !r.passed && r.severity === 'BLOCK');
  const flagged = results.filter((r) => r.severity === 'FLAG');

  let action = 'PUBLISH';
  if (blocked.length > 0) action = 'BLOCK';
  else if (flagged.length > 0) action = 'FLAG_AND_PUBLISH';

  return {
    postText: text,
    action,
    checks: results,
    blockedReasons: blocked.map((r) => r.message),
    flaggedReasons: flagged.map((r) => r.message),
    hash: duplicateCheck.hash || simpleHash(text.trim().toLowerCase()),
  };
}

/**
 * Run preflight checks on an entire batch of posts.
 *
 * @param {Array<object>} posts       - Array of post objects from claudeOutputValidator
 * @param {string} clientName
 * @param {Array}  recentPostHashes
 * @param {object} [config]
 *
 * @returns {{
 *   results: Array,
 *   batchAction: 'ALL_CLEAR' | 'PARTIAL_BLOCK' | 'ALL_BLOCKED',
 *   publishable: Array,
 *   blocked: Array,
 *   flagged: Array,
 *   summary: string
 * }}
 */
function runBatchPreflightChecks({ posts, clientName, recentPostHashes = [], config = DEFAULT_CONFIG }) {
  const results = posts.map((post) =>
    runPreflightChecks({
      text: post.text,
      clientName,
      recentPostHashes,
      config,
    })
  );

  const publishable = results.filter((r) => r.action !== 'BLOCK');
  const blocked     = results.filter((r) => r.action === 'BLOCK');
  const flagged     = results.filter((r) => r.action === 'FLAG_AND_PUBLISH');

  let batchAction = 'ALL_CLEAR';
  if (blocked.length === results.length) batchAction = 'ALL_BLOCKED';
  else if (blocked.length > 0)          batchAction = 'PARTIAL_BLOCK';

  const summary =
    `${publishable.length}/${results.length} posts cleared for scheduling. ` +
    (blocked.length > 0 ? `${blocked.length} blocked. ` : '') +
    (flagged.length > 0 ? `${flagged.length} flagged for operator review.` : '');

  return { results, batchAction, publishable, blocked, flagged, summary };
}

module.exports = {
  runPreflightChecks,
  runBatchPreflightChecks,
  checkPlaceholders,
  checkCharacterCount,
  checkProfanity,
  checkNotEmpty,
  checkDuplicate,
  checkNamedEntities,
  simpleHash,
};
