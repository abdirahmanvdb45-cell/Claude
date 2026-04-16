/**
 * airtable-schema.js
 *
 * Reference schema for all Airtable tables used in the LinkedIn content system.
 * Use this to set up your Airtable base manually or to validate field names
 * against n8n node parameters.
 *
 * Tables:
 *   1. clients
 *   2. voice_profiles
 *   3. content_log
 *   4. revision_log
 */

const AIRTABLE_SCHEMA = {
  /**
   * TABLE: clients
   * One record per paying client. Central state machine for the system.
   */
  clients: {
    fields: {
      client_id:                  { type: 'singleLineText', description: 'UUID generated at onboarding. Primary key.' },
      name:                       { type: 'singleLineText', description: 'Client full name.' },
      email:                      { type: 'email',          description: 'Primary contact email. Set to "bounced" string if bounce detected.' },
      status:                     {
        type: 'singleSelect',
        description: 'Current pipeline state. Only "scheduled_confirmed" is a clean published state.',
        options: [
          'active',
          'questionnaire_sent',
          'generating',
          'doc_delivered',
          'scheduling',
          'scheduled_confirmed',
          'scheduling_partial',
          'paused_emergency',
          'generation_failed',
          'email_failed',
          'cancelled',
        ],
      },
      plan_tier:                  { type: 'singleSelect', options: ['starter-8', 'growth-16', 'pro-20'] },
      taplio_account_id:          { type: 'singleLineText', description: 'Taplio account/profile ID for this client. Required for scheduling.' },
      last_content_generated:     { type: 'singleLineText', description: 'Format: YYYY-MM. Used to detect duplicate submissions and Day 8 fallback trigger.' },
      last_doc_id:                { type: 'singleLineText', description: 'Google Doc ID of the most recent content delivery doc.' },
      last_checked_time:          { type: 'dateTime',       description: 'ISO timestamp — used as cursor for comment polling to detect new comments only.' },
      questionnaire_sent_at:      { type: 'dateTime',       description: 'When the monthly questionnaire email was sent.' },
      posts_scheduled:            { type: 'number',         description: 'Count of posts confirmed scheduled this month.' },
      email_failed:               { type: 'dateTime',       description: 'Set when Resend delivery fails after all retries. Null if no failure.' },
      email_status:               { type: 'singleSelect',   options: ['ok', 'bounced', 'failed'] },
      is_fallback_this_month:     { type: 'checkbox',       description: 'True if this month used fallback generation (client missed questionnaire).' },
      paused_at:                  { type: 'dateTime',       description: 'Set when status changes to paused_emergency.' },
      resumed_at:                 { type: 'dateTime',       description: 'Set when status returns to active from paused_emergency.' },
      onboarded_at:               { type: 'dateTime',       description: 'When client was first created.' },
      cancelled_at:               { type: 'dateTime',       description: 'Triggers the GDPR data deletion workflow 60 days after being set.' },
    },
  },

  /**
   * TABLE: voice_profiles
   * One record per client. Stores the generated voice profile JSON and evolving data.
   */
  voice_profiles: {
    fields: {
      client_id:              { type: 'singleLineText', description: 'FK → clients.client_id' },
      voice_profile_json:     { type: 'longText',       description: 'JSON string of the 8-field voice profile. Parse before use in Claude prompt.' },
      best_performing_posts:  { type: 'longText',       description: 'JSON array of top 3 post objects by impressions. Populated from Month 3 onwards. Format: [{text, impressions, publishedAt}]' },
      past_topics_covered:    { type: 'longText',       description: 'JSON array of topic strings. Format: ["topic name — Month YYYY"]. Prevents repetition in fallback and future generation.' },
      profile_version:        { type: 'number',         description: 'Increments on each profile refresh (Month 6+).' },
      last_enriched:          { type: 'date',           description: 'Date of last best_performing_posts update.' },
    },
  },

  /**
   * TABLE: content_log
   * One record per monthly content batch per client.
   */
  content_log: {
    fields: {
      client_id:              { type: 'singleLineText', description: 'FK → clients.client_id' },
      month:                  { type: 'singleLineText', description: 'Format: YYYY-MM' },
      post_count_generated:   { type: 'number',         description: 'How many posts Claude generated.' },
      post_count_scheduled:   { type: 'number',         description: 'How many posts were confirmed scheduled in Taplio.' },
      scheduling_status:      {
        type: 'singleSelect',
        description: 'Scheduling outcome. scheduled_confirmed is the only fully clean state.',
        options: ['scheduled_confirmed', 'scheduling_partial', 'scheduling_failed'],
      },
      raw_claude_output:      { type: 'longText', description: 'Saved on generation failure or validation failure. Used for debugging and manual recovery.' },
      pending_generation:     { type: 'longText', description: 'Raw questionnaire answers saved when Claude fails. Used for retry.' },
      doc_url:                { type: 'url',      description: 'Google Doc URL for this month\'s content.' },
      is_fallback:            { type: 'checkbox', description: 'True if this batch was generated as fallback (no questionnaire submitted).' },
      approved_at:            { type: 'dateTime', description: 'When the client clicked Approve & Schedule.' },
      created_at:             { type: 'dateTime', description: 'When this content log record was created.' },
    },
  },

  /**
   * TABLE: revision_log
   * One record per Claude revision. Used for operator review and repeat-revision detection.
   */
  revision_log: {
    fields: {
      client_id:      { type: 'singleLineText', description: 'FK → clients.client_id' },
      revision_date:  { type: 'dateTime',       description: 'When the revision was made.' },
      comment_id:     { type: 'singleLineText', description: 'Google Docs comment ID. Used to count revisions per comment (max 2 before escalation).' },
      post_number:    { type: 'number',         description: 'Which post number in the batch (1–8, 1–16, etc.)' },
      original_text:  { type: 'longText',       description: 'Post text before Claude revised it.' },
      revised_text:   { type: 'longText',       description: 'Post text after Claude revised it.' },
      comment_text:   { type: 'longText',       description: 'The client\'s comment that triggered the revision.' },
      pass_number:    { type: 'number',         description: '1 = first revision, 2 = second. On 3rd attempt, workflow escalates to operator instead.' },
      confidence:     { type: 'singleSelect',   options: ['HIGH', 'MEDIUM', 'LOW'], description: 'Claude\'s confidence in the revision quality. LOW = operator should review.' },
    },
  },
};

/**
 * Validate that a given object has all required fields for an Airtable operation.
 *
 * @param {string} tableName - One of the keys in AIRTABLE_SCHEMA
 * @param {object} record    - The record object to validate
 * @param {string[]} required - Field names that must be present
 */
function validateRecord(tableName, record, required = []) {
  const schema = AIRTABLE_SCHEMA[tableName];
  if (!schema) throw new Error(`Unknown table: ${tableName}`);

  const missing = required.filter((field) => !(field in record) || record[field] === undefined || record[field] === null);

  if (missing.length > 0) {
    throw new Error(`Missing required fields for ${tableName}: ${missing.join(', ')}`);
  }
  return true;
}

/**
 * Valid status transitions for the clients table.
 * Used to prevent invalid state changes.
 */
const VALID_STATUS_TRANSITIONS = {
  active:               ['questionnaire_sent', 'generating', 'paused_emergency', 'cancelled'],
  questionnaire_sent:   ['generating', 'paused_emergency', 'cancelled'],
  generating:           ['doc_delivered', 'generation_failed', 'paused_emergency'],
  doc_delivered:        ['scheduling', 'paused_emergency', 'cancelled'],
  scheduling:           ['scheduled_confirmed', 'scheduling_partial', 'scheduling_failed'],
  scheduled_confirmed:  ['active', 'paused_emergency', 'cancelled'],
  scheduling_partial:   ['scheduled_confirmed', 'paused_emergency'],
  scheduling_failed:    ['scheduling', 'paused_emergency'],
  generation_failed:    ['generating', 'paused_emergency', 'cancelled'],
  email_failed:         ['doc_delivered', 'paused_emergency', 'cancelled'],
  paused_emergency:     ['active', 'cancelled'],
  cancelled:            [],
};

function isValidTransition(fromStatus, toStatus) {
  const allowed = VALID_STATUS_TRANSITIONS[fromStatus] || [];
  return allowed.includes(toStatus);
}

module.exports = { AIRTABLE_SCHEMA, validateRecord, isValidTransition, VALID_STATUS_TRANSITIONS };
