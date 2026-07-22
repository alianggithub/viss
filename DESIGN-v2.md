# YouTube Review Queue — Design v2

Date: 2026-07-16  
Status: Proposed design for implementation and live validation  
Supersedes: `DESIGN.md` v1.0 in `yt-queue-poc.zip`  
Prototype status: useful workflow simulation; not proof of live Google authentication or exact playback matching

## 1. Purpose

The system helps a user flag the part of a YouTube video that deserves later
attention while the user has limited access to a keyboard or computer.

The normal interaction is a short Telegram text or voice message:

```text
priority 5
priority 3 check the benchmark
priority 0
```

The system records the Telegram event immediately. After the corresponding
YouTube activity becomes available, it attempts to identify the video that was
playing and estimates the location in the video. It then presents a per-account,
newest-first review table. A resolved item may be classified against the current
contents of `~/knowledge_base/` and, when explicitly requested, sent through the
`llm_wiki` workflow.

This design supports multiple Telegram users and multiple Google/YouTube
accounts without placing account names in every command.

## 2. Design Principles

1. **Capture first.** A Telegram command must be stored durably before slow or
   failure-prone Google, YouTube, classification, or wiki work begins.
2. **Do not claim false precision.** Google activity timestamps indicate an
   activity time, not exact player telemetry. Derived in-video offsets are
   estimates unless an exact URL or companion integration supplied the offset.
3. **Keep identities explicit.** Telegram identity, application account, Google
   OAuth grant, and YouTube channel identity are related but distinct records.
4. **Use separate OAuth grants.** Google Data Portability scopes must not be
   combined with ordinary YouTube Data API or identity scopes in one grant.
5. **Treat ambiguity as data.** Keep candidate matches and confidence rather than
   silently selecting the first overlapping video.
6. **Make every background action retryable and idempotent.** Telegram retries,
   repeated exports, resolver runs, and wiki jobs must not duplicate records.
7. **Sort when reading.** “Latest on top” is a query and presentation rule, not a
   reason to rewrite a storage file on every insert.

## 3. Scope

### 3.1 Version 1 goals

- Receive priority commands through a Telegram bot.
- Use Telegram sender ID to select the correct application account.
- Record Telegram's event timestamp, note, priority, and update identifier.
- Resolve a video from Google YouTube activity after the activity is published.
- Show an account-isolated table ordered newest first.
- Represent estimated, exact, ambiguous, expired, and unresolved results.
- Support priority 0 as “do not watch again.”
- Classify resolved items against the live `~/knowledge_base/` structure.
- Run wiki generation only when explicitly requested or separately enabled.
- Enroll and verify at least two real Google accounts/channels.

### 3.2 Non-goals for the first release

- Reconstruct exact pause, seek, playback-speed, or multi-device behavior from
  YouTube activity history.
- Depend on the YouTube Watch History (`HL`) or Watch Later (`WL`) playlists via
  YouTube Data API; these are not available through the API.
- Automatically create new knowledge-base categories.
- Automatically publish wiki content solely because an item has high priority.
- Delete or alter the user's YouTube history.

## 4. Important Constraints

### 4.1 History availability

The ordinary YouTube Data API does not expose Watch History or Watch Later.
The primary automated source should be Google's Data Portability API using
`dataportability.myactivity.youtube`. A manual Google Takeout import remains a
fallback and a useful development fixture.

Data Portability is not real-time. A recurring export can generally be requested
at most once every 24 hours, and archive creation can take minutes or hours. The
design therefore promises eventual resolution, not immediate resolution.

### 4.2 Offset accuracy

If an activity record says a video was watched at time `S`, and the Telegram
message was created at `T`, then `T - S` is only an estimated offset. It may be
wrong because of pauses, seeks, playback speed, resumed playback, autoplay,
multiple tabs, multiple devices, delayed reactions, or activity timestamp
semantics.

An offset is exact only when supplied by a source that knows the player position,
such as:

- a YouTube share URL containing `t=...`;
- a browser/player companion that sends video ID and current time; or
- another integration that reads the active player's state with user consent.

### 4.3 OAuth separation

Use two independent grants per Google account when both capabilities are needed:

- `data_portability_grant`: retrieves YouTube My Activity exports;
- `youtube_data_grant`: calls YouTube Data API for channel verification and
  video metadata.

Do not request Data Portability scopes together with `youtube.readonly`,
`userinfo`, OpenID Connect, or other ordinary OAuth scopes. Tokens and secrets
must be stored in a secret store or protected credential files, never in YAML
committed to source control.

## 5. User Experience

### 5.1 Commands

| Command | Result |
|---|---|
| `priority N` | Capture the current viewing moment with priority 0–5. |
| `priority N <note>` | Capture it with a short note. |
| `priority 0` | Record as dismissed; do not add to the watch queue or auto-wiki. |
| `queue` | Show this account's newest items first. |
| `queue <id>` | Show details, match confidence, and candidates. |
| `choose <id> <candidate>` | Resolve an ambiguous item manually. |
| `link <id> <youtube-url>` | Resolve using a pasted URL; preserve a supplied timestamp. |
| `watched <id>` | Mark the review item watched. |
| `wiki <id>` | Request classification and wiki generation. |
| `wiki <id> as <category>` | Request wiki generation with an allowed category override. |
| `status` | Show capture, resolver, export, and wiki status. |

Voice transcription may normalize small-number words, for example “priority
five.” If priority or intent is ambiguous, the bot asks for clarification and
does not create a bookmark.

### 5.2 Capture acknowledgement

The bot responds only after the bookmark transaction commits:

```text
Saved Q7F2 (priority 5) at 14:32:08.
Waiting for YouTube activity; the eventual timestamp may be estimated.
```

Duplicate delivery of the same Telegram update returns the existing bookmark
rather than inserting a second one.

### 5.3 Ambiguous result

When two or more candidates are plausible, the bot does not silently choose:

```text
Q7F2 has two possible videos:
1. Model serving benchmark — estimated 12:41
2. GPU architecture overview — estimated 03:08
Reply: choose Q7F2 1
```

## 6. System Architecture

```text
Telegram Bot API
      |
      | update_id, from.id, message.date, text/voice transcript
      v
Capture service -----> SQLite database <----- Read-only queue UI / bot queries
                           |
                           v
                  Per-account resolver
                     /           \
       Data Portability API     Manual Takeout import
                     \           /
                      activity normalization
                           |
                    candidate matcher
                           |
             YouTube metadata enrichment
                           |
                  KB classification job
                           |
                 optional llm_wiki job
```

The Telegram request path performs parsing, authorization, and one database
transaction. History retrieval, matching, metadata calls, classification, and
wiki generation run in background jobs.

## 7. Identity and Multiple Accounts

### 7.1 Identity model

Do not use a user-editable account label as an authorization boundary. Model the
following separately:

- **Telegram principal:** Telegram numeric user ID, with active/disabled status.
- **Application account:** owns one queue and its policy/configuration.
- **Membership:** assigns a Telegram principal a role in an application account.
- **Google connection:** one enrolled Google authorization set.
- **YouTube channel:** channel ID returned by `channels.list(mine=true)` under the
  YouTube Data API grant.

A Telegram principal may belong to one or more application accounts. If it has
exactly one active membership, the bot selects it automatically. If it has more
than one, the bot uses a stored default or asks the user to select one.

### 7.2 Secure binding

The original prototype's unrestricted `use account <label>` flow must not be
used. Any whitelisted user who knows a label could otherwise bind to another
person's queue.

Membership is created by one of these mechanisms:

1. administrator approval;
2. a single-use, expiring invitation code scoped to one application account; or
3. an authenticated account-management UI.

Whitelist/active status is checked before membership lookup on every command.
Disabling a Telegram principal immediately revokes access even if an old mapping
still exists.

### 7.3 Enrollment and live proof

For each real Google connection:

1. Start Data Portability authorization and store its grant separately.
2. Start ordinary YouTube Data API authorization with offline access.
3. Call `channels.list(part=id,snippet, mine=true)`.
4. Store and display the returned channel ID/title for user confirmation.
5. Request or ingest that account's own activity export.
6. Confirm that its history and bookmarks remain isolated from another account.

The multi-account milestone is complete only after this succeeds for at least two
real accounts (or two real channels with clearly documented Google-account
behavior). Constructing two in-memory `Credentials` objects with synthetic tokens
is a unit test, not authentication proof.

Data Portability authorization does not provide a normal identity claim. The
enrollment flow must bind the opaque grant to the application account through an
authenticated, single-use enrollment session and user confirmation.

## 8. Storage Model

Use SQLite in WAL mode for the first deployment. It gives atomic capture,
concurrent readers, uniqueness constraints, migrations, and reliable newest-first
queries without introducing a database service. PostgreSQL is a straightforward
upgrade if the system later runs on multiple hosts.

### 8.1 Core tables

#### `app_account`

| Field | Notes |
|---|---|
| `id` | Internal UUID or integer key. |
| `display_name` | Human-readable, not an authorization secret. |
| `timezone` | Presentation only; timestamps remain UTC. |
| `created_at`, `disabled_at` | Lifecycle. |

#### `telegram_principal`

| Field | Notes |
|---|---|
| `telegram_user_id` | Numeric stable Telegram sender ID; primary key. |
| `display_name` | Last observed display name, informational only. |
| `active` | Authorization gate. |

#### `account_membership`

| Field | Notes |
|---|---|
| `app_account_id`, `telegram_user_id` | Unique pair. |
| `role` | `owner`, `member`, or `viewer`. |
| `is_default` | At most one default per Telegram principal. |

#### `google_connection`

| Field | Notes |
|---|---|
| `id`, `app_account_id` | Connection ownership. |
| `youtube_channel_id`, `youtube_channel_title` | Verified using YouTube Data API. |
| `data_portability_credential_ref` | Reference to protected credentials. |
| `youtube_data_credential_ref` | Separate protected credential reference. |
| `grant_expires_at`, `last_export_at`, `last_success_at` | Health/status. |

#### `bookmark`

| Field | Notes |
|---|---|
| `id` | Stable public-friendly identifier. |
| `app_account_id` | Required isolation key. |
| `telegram_update_id` | Unique with bot identity for idempotency. |
| `telegram_user_id` | Capturing principal for audit. |
| `captured_at` | Telegram `message.date`, normalized to UTC. |
| `received_at` | Server receipt time, UTC. |
| `priority` | Integer 0–5. |
| `note` | User text after the command. |
| `source_state` | Resolution state below. |
| `watch_state` | Review state below. |
| `selected_match_id` | Nullable selected candidate. |
| `created_at`, `updated_at` | Database audit fields. |

#### `activity_event`

| Field | Notes |
|---|---|
| `id`, `google_connection_id` | Source ownership. |
| `source` | `data_portability` or `takeout`. |
| `source_event_key` | Stable hash/identifier for deduplication. |
| `activity_at` | Exported activity timestamp in UTC. |
| `video_id`, `title`, `channel_name` | Normalized fields. |
| `raw_payload_hash` | Audit/debug reference; raw data is access-controlled. |

#### `match_candidate`

| Field | Notes |
|---|---|
| `id`, `bookmark_id`, `activity_event_id` | Relationship. |
| `estimated_offset_s` | Nullable and explicitly estimated. |
| `offset_accuracy` | `unknown`, `estimated`, or `exact`. |
| `confidence` | Numeric score plus versioned algorithm. |
| `reason_json` | Timing differences and applied signals. |
| `selected_at`, `selected_by` | Automatic or manual decision audit. |

#### `video_metadata`

| Field | Notes |
|---|---|
| `video_id` | Primary key. |
| `title`, `channel_id`, `channel_title`, `duration_s` | Nullable if unavailable. |
| `fetched_at`, `fetch_status` | Cache freshness/error state. |

#### `knowledge_job`

| Field | Notes |
|---|---|
| `bookmark_id` | Target. |
| `kb_category`, `classification_confidence` | Classification result. |
| `wiki_state` | State below. |
| `wiki_requested_at`, `wiki_generated_at` | Full UTC timestamps. |
| `article_path`, `content_hash` | Result and idempotency. |
| `error_code`, `last_attempt_at`, `attempt_count` | Retry visibility. |

### 8.2 State dimensions

Keep independent state dimensions rather than one overloaded `status` field:

```text
source_state:
  awaiting_history | candidate | resolved_estimated | resolved_exact |
  ambiguous | expired

watch_state:
  queued | dismissed | watched

wiki_state:
  not_requested | queued | generated | failed
```

On capture, priority 0 sets `watch_state=dismissed`; priorities 1–5 set
`watch_state=queued`. A dismissed item may still be resolved for historical
context, but classification and wiki generation are skipped unless explicitly
requested.

### 8.3 Latest-first table

Every queue view uses:

```sql
SELECT ...
FROM bookmark
WHERE app_account_id = ?
ORDER BY captured_at DESC, id DESC;
```

The database's physical row order is irrelevant. Pagination uses the same stable
keyset ordering.

## 9. Capture Pipeline

1. Verify Telegram webhook authenticity and configured secret path/token.
2. Deduplicate by bot identity plus `update_id`.
3. Read `message.from.id` and reject inactive principals before membership lookup.
4. Select the sole/default application account, or request account selection.
5. Parse priority and optional note from text or voice transcript.
6. Use Telegram `message.date` for `captured_at`; record server time separately.
7. Insert the bookmark transactionally.
8. Return its stable ID.

Do not use local processing time as the viewing timestamp. Queue delays or bot
outages would otherwise shift the match.

## 10. Activity Acquisition

### 10.1 Primary: Data Portability API

Use the YouTube My Activity portability scope. The resolver scheduler operates per
Google connection:

1. check grant health and export eligibility;
2. request a new export only when allowed;
3. poll the export job with bounded exponential backoff;
4. download and verify the completed archive;
5. retain minimal raw material according to a configured privacy policy;
6. normalize records into `activity_event` with a unique source key;
7. run candidate matching for unresolved bookmarks in the export's time range.

Renewal and consent duration are user-visible. Testing-mode OAuth is not suitable
for dependable recurring operation because testing credentials may expire
quickly. Production access may require app verification, security review, and
regional eligibility work.

### 10.2 Fallback: manual Takeout

The operator may import a Takeout archive for a specified connection. Import must:

- validate the expected account/connection with user confirmation;
- reject unexpectedly high malformed-record rates;
- preserve original timezone-aware timestamps and normalize to UTC;
- deduplicate repeated archive contents;
- report the covered date range and newest activity time; and
- never invent a video duration when it is missing.

Manual Takeout is not presented as a low-latency automated workflow.

### 10.3 Optional exact sources

Support these without changing the bookmark model:

- Telegram message includes a timestamped YouTube URL;
- user shares the current URL into Telegram;
- a browser companion sends `{video_id, player_offset_s, observed_at}`;
- a custom “Agent Inbox” YouTube playlist supplies an exact video ID, though not
  necessarily an exact playback offset.

## 11. Matching Algorithm

### 11.1 Candidate generation

For an unresolved bookmark at capture time `T`, retrieve nearby activity events
for the same Google connection. Do not use a fabricated default duration such as
600 seconds. If duration is unknown, calculate only signals that do not depend on
duration and keep confidence low until metadata is available.

For each event, collect signals such as:

- signed difference between `T` and activity time;
- whether `T` falls within a duration-based window, when duration is known;
- preceding/following activity events and impossible overlap;
- repeated watches of the same video;
- account and device/integration evidence, when available;
- a user-provided URL, video title, or note clue.

### 11.2 Scoring and decision

Store every plausible candidate with an algorithm version and explanation. Initial
thresholds must be calibrated against real user data rather than declared proven
by synthetic fixtures.

Suggested policy:

- no candidate: remain `awaiting_history` until expiry;
- one clearly dominant candidate: `resolved_estimated`;
- multiple close candidates: `ambiguous` and ask the user;
- timestamped URL/player telemetry: `resolved_exact`;
- beyond the configured activity-retention window: `expired`.

Asymmetric reaction windows may be useful (for example, a tighter allowance
before an activity and a looser one afterward), but values such as 30/120 seconds
are configuration starting points, not universal facts.

### 11.3 URL construction

For a selected video:

```text
https://youtu.be/<video_id>?t=<offset_seconds>
```

Include `t` only when an offset exists. Clamp an estimated offset to a known video
duration, but retain the unclamped calculation in match diagnostics. Display an
“estimated” label wherever the URL includes an inferred offset.

## 12. Metadata and Classification

Use YouTube Data API `videos.list(part=snippet,contentDetails, id=...)` in batches
to fetch titles, channel information, and durations. Cache results and represent
deleted, private, or unavailable videos without discarding the bookmark.

Classification runs only after resolution unless the user explicitly requests an
early/manual classification.

At job time:

1. enumerate allowed categories from the current `~/knowledge_base/` structure;
2. read the relevant schemas/indexes required by the knowledge-base workflow;
3. classify using title, channel, description/transcript where available, and the
   user's note;
4. save category and confidence;
5. return “unclassified” when evidence is weak instead of inventing a category.

Do not hard-code the category list from the prototype because the knowledge base
will evolve.

## 13. Wiki Workflow

Priority expresses review importance, not consent to publish or mutate the
knowledge base. Wiki intent is a separate flag or command. A per-account setting
may enable automatic wiki requests only after the owner explicitly opts in.

For an authorized wiki request:

1. verify the bookmark is resolved and not dismissed, unless manually overridden;
2. classify or validate the requested category;
3. follow the installed `llm_wiki` workflow and the target KB's own schema;
4. collect permitted source material and preserve source attribution;
5. run any required health/safety checks before editing;
6. write the page and navigation changes;
7. save `wiki_generated_at` as a full timestamp and `article_path`;
8. make the job idempotent using `(bookmark_id, content_hash)`;
9. report the result or actionable failure through Telegram.

Retrying a timed-out callback must not create a second article. A changed source
or prompt creates a new content hash and should use an explicit update flow.

## 14. Security and Privacy

- Authorize from numeric Telegram sender ID, never username or display name.
- Check active/whitelist status before membership or account routing.
- Do not allow unrestricted self-binding by account label.
- Store OAuth refresh tokens outside source control with least-privilege file or
  secret-manager access.
- Keep Data Portability and YouTube Data credentials separate.
- Encrypt sensitive credentials at rest when the deployment supports it.
- Minimize retention of raw My Activity and Takeout data; document deletion rules.
- Redact tokens, Telegram IDs, raw activity, and private notes from logs.
- Apply account ID filters in every queue, activity, match, and job query.
- Use parameterized SQL and validate YouTube IDs/URLs.
- Record administrative binding and credential changes in an audit log.
- Scan tracked files for credential patterns before any push.
- Back up the database and test restoration; protect backups like the live data.

## 15. Reliability and Observability

Background work uses durable jobs with bounded retries and dead-letter/error state.
Useful per-account status includes:

- most recent Telegram capture and update ID;
- most recent successful activity export/import and covered time range;
- bookmarks awaiting history, ambiguous, estimated, exact, and expired;
- OAuth/grant expiration or renewal date;
- metadata and wiki job failures;
- resolver algorithm version.

Alerts should distinguish expected history latency from broken authorization or a
parser-format change. Never convert an expected empty export into a permanent
failure after one attempt.

## 16. Configuration

Non-secret configuration may include:

```yaml
resolver:
  schedule: daily
  expiry_days: 14
  candidate_window_before_s: 30
  candidate_window_after_s: 120
  auto_select_min_confidence: 0.90
  ambiguity_margin: 0.10

wiki:
  auto_request: false

privacy:
  raw_activity_retention_days: 30
```

Thresholds are versioned and adjusted using real labeled matches. Credentials and
refresh tokens do not belong in this file.

## 17. Implementation Layout

```text
yt-review-queue/
├── pyproject.toml
├── uv.lock                         # or another committed lock file
├── migrations/
├── src/yt_review_queue/
│   ├── telegram_webhook.py
│   ├── commands.py
│   ├── identity.py
│   ├── capture.py
│   ├── data_portability.py
│   ├── takeout_import.py
│   ├── activity_normalize.py
│   ├── matcher.py
│   ├── youtube_metadata.py
│   ├── classify.py
│   └── wiki_job.py
├── tests/
│   ├── fixtures/
│   ├── unit/
│   └── integration/
└── var/                            # ignored runtime data for local deployment
    └── queue.sqlite3
```

Declare the supported Python version explicitly. The prototype uses language and
library features unavailable in the host's legacy default Python, so deployment
must invoke the selected modern runtime and install locked dependencies.

## 18. Phased Delivery and Acceptance Criteria

### Phase 0 — Correct the prototype baseline

- Add a declared modern Python runtime and locked dependencies.
- Replace CSV persistence with SQLite and migrations.
- Fix whitelist-before-membership authorization.
- Remove unrestricted account self-binding.
- Store Telegram event time and enforce update-ID idempotency.
- Add automated tests instead of claiming an absent “8/8” suite.

**Accepted when:** tests demonstrate duplicate Telegram delivery, concurrent
capture/resolution, account isolation, disabled-user rejection, and stable
newest-first queries.

### Phase 1 — Durable Telegram capture

- Implement webhook parsing, authorization, command handling, and queue/status.
- Support text and normalized voice transcripts.
- Make priority 0 dismissed at capture time.

**Accepted when:** two authorized Telegram principals route to the intended
accounts, unauthorized or disabled principals cannot read/write queues, and a
replayed update does not duplicate a bookmark.

### Phase 2 — Real multi-account OAuth prototype

- Configure separate OAuth clients/grants as required.
- Enroll two real Google/YouTube accounts.
- Verify each channel with `channels.list(mine=true)`.
- Store distinct credential references and demonstrate token refresh.

**Accepted when:** channel IDs are confirmed by their owners and metadata/history
from one connection cannot appear in the other's account.

### Phase 3 — Activity acquisition

- Integrate Data Portability for YouTube My Activity.
- Keep a validated, deduplicating manual Takeout importer.
- Expose export latency, coverage, and grant health in `status`.

**Accepted when:** a real activity from each test account is normalized with its
original time and rerunning the same import creates no duplicate.

### Phase 4 — Confidence-aware resolution

- Implement duration/metadata enrichment without fake durations.
- Generate and persist candidates with explainable scores.
- Add estimated/exact/ambiguous/expired flows and manual selection.
- Calibrate thresholds on labeled real sessions including pause, seek, resume,
  autoplay, and two-device cases.

**Accepted when:** the UI labels inferred offsets as estimated, ambiguous cases
are not silently selected, and exact timestamped URLs remain exact.

### Phase 5 — Knowledge-base integration

- Discover current categories dynamically.
- Implement classification with confidence and an unclassified outcome.
- Add explicit, idempotent wiki requests and full generation timestamps.

**Accepted when:** a retry cannot create duplicate wiki pages and priority alone
does not trigger KB mutation unless the account owner opted in.

### Phase 6 — Operations and usability

- Add monitoring, backups/restoration, retention cleanup, and grant-renewal flows.
- Provide a small read-only web table or Telegram pagination, newest first.
- Optionally add a timestamped-share or browser companion for exact captures.

**Accepted when:** a full capture-to-review workflow survives process restart,
expected export latency, repeated callbacks, and credential renewal.

## 19. Test Matrix

At minimum, automate these cases:

- valid text/voice priorities 0–5 and ambiguous commands;
- duplicate and out-of-order Telegram updates;
- revoked whitelist with stale membership;
- attempted cross-account binding and access;
- one principal with multiple accounts/default selection;
- repeated/overlapping Takeout or Data Portability imports;
- missing, private, deleted, live, and extremely long videos;
- unknown duration without a fabricated default;
- pause, seek, playback speed, resume, autoplay, and simultaneous devices;
- no candidate, one strong candidate, close candidates, and expired history;
- metadata/API rate limits, token expiry, export failure, and parser changes;
- wiki retry, content-hash change, and partial-edit recovery;
- timezone and daylight-saving boundaries;
- database restart, migration, backup, and restore.

Synthetic fixtures are appropriate for edge cases, but live Google acceptance
tests must be reported separately and must not expose real tokens or activity data.

## 20. Decisions Still Needed

1. Whether the first deployment should pursue Data Portability production access
   immediately or begin with manual Takeout while approval is in progress.
2. Whether the exact-capture option should be a shared timestamped URL, an “Agent
   Inbox” playlist, or a browser companion.
3. Whether one Telegram principal may switch among multiple application accounts.
4. Raw activity retention duration and backup location.
5. Whether any account opts into automatic wiki requests; the default is off.
6. Whether the table is Telegram-only initially or also a small authenticated web
   view.

## 21. Official References

- Google Data Portability overview: <https://developers.google.com/data-portability/user-guide/overview>
- Data Portability scopes: <https://developers.google.com/data-portability/user-guide/scopes>
- Data Portability methods: <https://developers.google.com/data-portability/user-guide/methods>
- YouTube My Activity schema: <https://developers.google.com/data-portability/schema-reference/my_activity?hl=en>
- Data Portability time filters: <https://developers.google.com/data-portability/user-guide/time-filter>
- Data Portability OAuth configuration: <https://developers.google.com/data-portability/user-guide/configure-oauth>
- YouTube `channels.list`: <https://developers.google.com/youtube/v3/docs/channels/list>
- YouTube `playlistItems.list`: <https://developers.google.com/youtube/v3/docs/playlistItems/list>
- YouTube Data API revision history: <https://developers.google.com/youtube/v3/revision_history>
- Google OAuth offline access: <https://developers.google.com/identity/protocols/oauth2/web-server>
- Telegram Bot API: <https://core.telegram.org/bots/api>
- Google Takeout help: <https://support.google.com/accounts/answer/3024190?hl=en-EN>

## 22. Changes from v1

- Replaces repeated manual Takeout as the primary path with Data Portability,
  retaining Takeout as fallback.
- Separates Data Portability and YouTube Data OAuth grants.
- Changes “multi-account proven” to a live two-account acceptance requirement.
- Replaces CSV files with transactional SQLite storage.
- Replaces unrestricted self-binding with memberships and controlled enrollment.
- Uses Telegram `message.date` and `update_id`, not local processing time alone.
- Models resolution, watch, and wiki state independently.
- Labels history-derived offsets as estimated and retains ambiguous candidates.
- Removes fabricated default video duration behavior.
- Treats 30/120-second tolerance as a tunable starting point, not a proven rule.
- Decouples high priority from automatic wiki mutation.
- Adds idempotency, retention, audit, observability, runtime, migration, and live
  acceptance requirements.
