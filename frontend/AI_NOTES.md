# Frontend AI notes

- 2026-11-06: Codex built the first React/Vite landing and navigation shell from the user's art direction. The user supplied the 21st theme screenshot, halftone reference, and Hyperiux scramble-button source. Codex adapted the scramble interaction for links and buttons, made an original CSS pointer-reactive script wordmark, and added the dark/light ripple. User review pending. No backend integration is claimed.

Reference: [Halftone Wordmark Footer](https://21st.dev/@kedhareswer/components/halftone-wordmark-footer) (MIT); [Hyperiux Vault](https://vault.hyperiux.com) scramble-button source supplied by the user.

- 2026-11-06: After the user's review, Codex removed the halftone cursive wordmark, cursor circle, scroll cues, small decorative copy, and unfinished app destinations. Rebuilt the landing page with large plain type, an illustrative bot-history panel, three concise explanations, and a three-link menu. User review pending. No backend integration is claimed.

- 2026-11-06: Codex audited the landing page after the user reported a glitching theme ripple. Replaced the solid overlay and timer with a View Transition reveal of the actual new page, guarded against repeat clicks, removed non-clickable arrows from the illustration, improved narrow-screen heading sizing, and kept background content inert while the menu is open. Checked dark/light transition and phone-width layout in Chrome. User review pending.

- 2026-11-06: After another user review, Codex removed the small uppercase decorative labels and em dash or middle dot punctuation from visible frontend copy. Added stronger theme-aware borders to cards and buttons. Fixed text-scramble layout movement by reserving each button's full label width and resetting the text when the pointer leaves. Checked the updated landing and menu in Chrome. User review pending.

- 2026-11-06: Codex completed Claude Code's theme-switch checklist: the saved theme is applied in the HTML head before React mounts, the View Transition snapshots the new theme, and the CSS reveals that page from the click point. Added a browser-environment test for browsers without View Transitions. User review pending.

- 2026-11-06: Codex linked the React landing and menu to the existing `/classic` bot-launch page, and proxied that route and its static assets in Vite development. No engine code changed.
