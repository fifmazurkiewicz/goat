# Plan: mobile layout (Android / iOS) — 2026-08-16

## Problem

On phones the chat history was not visible right away. Other screens: too large gutter, lack of safe area, touch < 44px.

## Decisions

| Date | Decision | Why |
|------|---------|-----|
| 2026-08-16 | Variant A: lock the chat viewport (`dvh` + visualViewport, `main overflow-hidden` only on `/chat`, pin history at the bottom) | Fixes the reported bug without changing IA |
| 2026-08-16 | No MessageList virtualization in MVP | `estimateSize: 88` broke first paint |
| 2026-08-16 | Bottom nav deferred | Conscious IA change; not mixed with the height hotfix |
| 2026-08-16 | Safe area + `PAGE_SHELL_CLASS` on the remaining pages | One layout change fixes many screens |
| 2026-08-16 | `useIsMobile` = width <768 **or** height <500 | iPhone landscape doesn't get a desktop Dialog / month grid |
| 2026-08-16 | Input/textarea `text-base` on mobile | Safari doesn't zoom on focus (font ≥16px) |
| 2026-08-16 | `ResponsiveDialog`: one scroll, footer shrink-0 + safe area | Keyboard doesn't hide Save |

## Given / When / Then

- Given an open session with history on phone, When the user enters `/chat/:id`, Then the latest messages are in frame, the Send field is visible.
- Given iOS/Android keyboard, When the user focuses the composer, Then the layout shrinks with visualViewport, history stays above the keyboard.
- Given `/plans` / `/results` / `/personas` / `/profile` / `/settings`, When the user scrolls, Then content is not cut off by the home indicator.
- Given iPhone landscape, When the user opens a persona form, Then they see a Sheet (not a centered Dialog).
- Given focus in a chat field on iOS, When the keyboard appears, Then the page doesn't zoom (font ≥16px).
