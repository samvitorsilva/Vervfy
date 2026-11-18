# UI components

This project uses TypeScript and the `@/*` alias maps to `src/*`. Shared UI
components therefore belong in `src/components/ui` (the project's equivalent
of `/components/ui`), so imports such as `@/components/ui/password-strength`
and the shadcn CLI resolve to the same folder. Do not create a second root
`components/ui` directory.

Global application styles are in `src/app/styles.css` and `src/app/auth.css`.
Tailwind v4 is configured through `postcss.config.mjs` and
`src/app/tailwind.css`, imported in the root layout. Its Preflight reset is
omitted to preserve existing styling; utilities are unlayered to override the
legacy global reset. Dark variants follow the operating system preference or a `.dark` ancestor.
The meter is rendered on signup and password reset, with `.dark` matching the
application theme.

`components.json` configures shadcn paths and `src/lib/utils.ts` supplies `cn`.
To add other shadcn components, run `npx shadcn@latest add <component>` from
`web`. For a new project without configuration, run `npx shadcn@latest init`.
No TypeScript setup is needed here.

Render the supplied interactive demo in a client or server component:

```tsx
import { PasswordStrengthDemo } from "@/components/ui/demo";

export default function Example() {
  return <PasswordStrengthDemo />;
}
```

For an existing controlled password input, render
`<PasswordStrength value={password} className="mt-3" />` beneath it.
The default rules are strength guidance, not server password validation.
Existing authentication forms retain their current validation policy.

The announcement timer clears empty input immediately in the returned state,
with internal state updates deferred to avoid synchronous effect updates.
