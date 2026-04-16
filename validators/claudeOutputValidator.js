/**
 * claudeOutputValidator.js
 *
 * Validates Claude's raw content generation output before a Google Doc
 * is ever created. If validation fails, the doc pipeline is halted and
 * a retry is triggered with a reinforced format prompt.
 *
 * Used in: n8n Function node — Step 6 (between Claude API call and Doc creation)
 * Runtime: Node.js (n8n built-in)
 */

const SEPARATOR_PATTERN = /---POST \d+---/g;
const POST_SPLIT_PATTERN = /---POST \d+---/;
const PLACEHOLDER_PATTERN = /\[NAME\]|\[DATE\]|\[INSERT\]|\[CLIENT\]|\{\{|\}\}/i;
const POSTING_TIME_PATTERN = /POSTING TIME:/i;
const CHAR_COUNT_PATTERN = /CHARACTER COUNT:/i;

/**
 * Parse raw Claude output into structured post objects.
 *
 * @param {string} rawOutput - The full text returned by Claude API
 * @returns {{ posts: Array<{number: number, text: string, postingTime: string, characterCount: number}>, separatorsFound: number }}
 */
function parseClaudeOutput(rawOutput) {
  const separatorsFound = (rawOutput.match(SEPARATOR_PATTERN) || []).length;

  const rawPosts = rawOutput
    .split(POST_SPLIT_PATTERN)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  const posts = rawPosts.map((block, index) => {
    const lines = block.split('\n');
    const postingTimeLine = lines.find((l) => POSTING_TIME_PATTERN.test(l)) || '';
    const charCountLine = lines.find((l) => CHAR_COUNT_PATTERN.test(l)) || '';

    // Extract post body — everything before the metadata lines
    const metadataStart = lines.findIndex(
      (l) => POSTING_TIME_PATTERN.test(l) || CHAR_COUNT_PATTERN.test(l)
    );
    const bodyLines = metadataStart > -1 ? lines.slice(0, metadataStart) : lines;
    const text = bodyLines.join('\n').trim();

    const postingTimeMatch = postingTimeLine.match(/POSTING TIME:\s*(.+)/i);
    const charCountMatch = charCountLine.match(/CHARACTER COUNT:\s*(\d+)/i);

    return {
      number: index + 1,
      text,
      postingTime: postingTimeMatch ? postingTimeMatch[1].trim() : null,
      characterCount: charCountMatch ? parseInt(charCountMatch[1], 10) : text.length,
      isFallback: text.startsWith('[FALLBACK]'),
    };
  });

  return { posts, separatorsFound };
}

/**
 * Run all validation checks on parsed posts.
 *
 * @param {Array} posts - Parsed post objects
 * @param {number} expectedCount - How many posts Claude was asked to generate
 * @returns {{ issues: Array<{severity: string, code: string, message: string}>, passed: boolean }}
 */
function validatePosts(posts, expectedCount) {
  const issues = [];

  // Check 1: Complete parse failure — no posts found at all
  if (posts.length === 0) {
    issues.push({
      severity: 'CRITICAL',
      code: 'NO_POSTS_PARSED',
      message:
        'Zero posts parsed — separator pattern "---POST N---" not found in Claude output. ' +
        'Claude likely used a different format. Retry with reinforced separator prompt.',
    });
    // Cannot proceed with further checks
    return { issues, passed: false };
  }

  // Check 2: Low post count (less than 75% of expected)
  if (posts.length < Math.floor(expectedCount * 0.75)) {
    issues.push({
      severity: 'CRITICAL',
      code: 'LOW_POST_COUNT',
      message: `Expected ${expectedCount} posts, parsed ${posts.length}. ` +
        'Output may have been truncated (max_tokens) or separator format broke partway through.',
    });
  }

  // Check 3: Per-post validation
  posts.forEach((post, i) => {
    const n = post.number;

    // Empty or too short
    if (!post.text || post.text.length < 50) {
      issues.push({
        severity: 'ERROR',
        code: 'POST_TOO_SHORT',
        message: `Post ${n}: Text is ${post.text ? post.text.length : 0} chars — minimum is 50. ` +
          'Likely a truncation or parse error.',
      });
    }

    // Character limit exceeded
    if (post.text && post.text.length > 3000) {
      issues.push({
        severity: 'ERROR',
        code: 'POST_TOO_LONG',
        message: `Post ${n}: Text is ${post.text.length} chars — LinkedIn limit is 3,000.`,
      });
    }

    // Unfilled placeholder
    if (post.text && PLACEHOLDER_PATTERN.test(post.text)) {
      const matches = post.text.match(/\[[\w\s]+\]|\{\{[\w\s]+\}\}/g) || [];
      issues.push({
        severity: 'ERROR',
        code: 'UNFILLED_PLACEHOLDER',
        message: `Post ${n}: Contains unfilled placeholder(s): ${matches.join(', ')}`,
      });
    }

    // Missing posting time
    if (!post.postingTime) {
      issues.push({
        severity: 'WARNING',
        code: 'MISSING_POSTING_TIME',
        message: `Post ${n}: No posting time found. Will use default schedule.`,
      });
    }
  });

  // Check 4: Duplicate posts within the batch
  const texts = posts.map((p) => p.text);
  const duplicates = texts.filter((text, i) => texts.indexOf(text) !== i);
  if (duplicates.length > 0) {
    issues.push({
      severity: 'ERROR',
      code: 'DUPLICATE_POSTS_IN_BATCH',
      message: `${duplicates.length} duplicate post(s) detected within this batch. Claude repeated content.`,
    });
  }

  const criticalOrError = issues.filter((i) => i.severity === 'CRITICAL' || i.severity === 'ERROR');
  return {
    issues,
    passed: criticalOrError.length === 0,
  };
}

/**
 * Main entry point.
 *
 * @param {string} rawOutput - Raw string from Claude API response
 * @param {number} expectedCount - Number of posts requested
 * @returns {{
 *   passed: boolean,
 *   posts: Array,
 *   issues: Array,
 *   shouldRetry: boolean,
 *   retryReason: string|null
 * }}
 */
function validateClaudeOutput(rawOutput, expectedCount) {
  if (!rawOutput || typeof rawOutput !== 'string' || rawOutput.trim().length === 0) {
    return {
      passed: false,
      posts: [],
      issues: [{ severity: 'CRITICAL', code: 'EMPTY_RESPONSE', message: 'Claude returned an empty response.' }],
      shouldRetry: true,
      retryReason: 'Empty response from Claude API.',
    };
  }

  const { posts, separatorsFound } = parseClaudeOutput(rawOutput);
  const { issues, passed } = validatePosts(posts, expectedCount);

  // Decide whether a retry makes sense
  const criticalCodes = issues.filter((i) => i.severity === 'CRITICAL').map((i) => i.code);
  const shouldRetry =
    criticalCodes.includes('NO_POSTS_PARSED') ||
    criticalCodes.includes('LOW_POST_COUNT');

  const retryReason = shouldRetry
    ? issues
        .filter((i) => i.severity === 'CRITICAL')
        .map((i) => i.message)
        .join(' | ')
    : null;

  return { passed, posts, issues, shouldRetry, retryReason, separatorsFound };
}

/**
 * Returns the reinforced format suffix to append to the original prompt on retry.
 */
function getRetryPromptSuffix() {
  return `

---

CRITICAL FORMATTING REQUIREMENT — READ BEFORE GENERATING:

Your previous response could not be parsed. You MUST use exactly this separator before each post:

---POST 1---
---POST 2---
---POST 3---

Rules:
- The separator must be on its own line
- It must start with three hyphens, then POST, then a space, then the number, then three hyphens
- Do not add asterisks, bold, brackets, or any other characters around it
- Do not skip any post numbers
- Begin your response with ---POST 1--- and nothing before it
- Do not add a summary, introduction, or closing remark

The parser is regex-based. Any deviation from the exact format above will cause a complete parse failure.
`;
}

// n8n Function node export
// In n8n, access input with $input.first().json
module.exports = { validateClaudeOutput, parseClaudeOutput, validatePosts, getRetryPromptSuffix };
