# Goat — approval notification design

## Goal

Notify `fifmazurkiewicz@gmail.com` once when a newly created, non-admin Goat profile enters the existing approval queue. The administrator can set the existing monthly USD usage budget and accept the account from the existing admin page.

## Scope and configuration

- This design is Goat-only; it does not call another application or shared notification service.
- Add backend-only `RESEND_API_KEY`, `RESEND_MAIL=fifmazurkiewicz@gmail.com`, and `RESEND_FROM=Powiadomienia <powiadomienia@fmazurkiewicz.dev>` settings. The Resend key is a Goat-specific sending-only key.
- Correct the sole-admin value and all defaults from `fmazurkiewicz@gmail.com` to `fifmazurkiewicz@gmail.com`; `ADMIN_EMAILS` remains the extension allowlist.

## Flow

The Supabase `handle_new_user` trigger creates `profiles` at signup, before the Goat backend sees the account. The authenticated account-read boundary therefore atomically claims a non-admin row whose notification status is still `pending`, then sends one transactional email through Resend. The claim and status update must use a conditional database update, so concurrent initial account reads cannot send duplicates. Later account reads and calls to `ProfilesRepo.ensure` must not create another notification. The mail contains only the application name, new account email, creation time, current default monthly USD budget, and the existing `/admin` URL.

Resend failure never blocks login, profile creation, the waiting screen, or the 403 feature gate. Store `pending`, `sent`, or `failed`, a sent timestamp, and a safe error summary. The admin-users response exposes that status. The existing admin table adds a retry action for `failed` or unsent notifications; retry is admin-only and updates the same record. No automatic retry is added.

The existing `PendingApprovalScreen` adds an accessible `mailto:fifmazurkiewicz@gmail.com` link with an app-specific subject. It does not expose feature navigation.

## Data, security, and UI

- Add notification state through a Supabase migration, never storing the Resend key, message body, or raw provider response.
- Do not send for the sole-admin/allowlisted accounts, approved profiles, or previously-notified profiles.
- Keep the Resend call in a small backend adapter with an injectable transport for tests; never import it in the frontend or commit a key.
- Reuse `usage_budget_usd` and the existing approval action. No token-count limit is introduced.

## Tests and rollout

Test new non-admin profile creation sends exactly one mail; a later `ensure` sends none; a provider error leaves the profile pending and records `failed`; an admin retry sends once; non-admin retry is forbidden; and the pending screen contains the contact link. Configure the three environment variables in Goat deployment before enabling the release, then create a test account and confirm one mail and manual acceptance.
