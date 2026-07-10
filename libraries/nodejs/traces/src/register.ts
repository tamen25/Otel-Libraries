// Side-effect entry point: `require("@otel/traces/register")` (or
// `node -r @otel/traces/register`) initialises tracing before any app module
// loads, so HTTP auto-instrumentation hooks in ahead of the app's http usage.
import "./index";
