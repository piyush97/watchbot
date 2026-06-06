# X/Twitter Source Options

WatchBot has a native X/Twitter monitor through `xurl`. Keep that path when the
user wants a compact health snapshot, keyword count, timeline count, dashboard
card, or alert inside Hermes.

Use TweetClaw as an optional companion when the user also runs OpenClaw and
needs broader X/Twitter work before or after a WatchBot check:

- Search tweets or search tweet replies with structured result limits.
- Look up users, user tweets, lists, communities, articles, or trends.
- Export followers or run giveaway draws for campaign review.
- Create explicit monitors and webhooks for recurring X/Twitter events.
- Post tweets, post tweet replies, send DMs, or manage media only after user
  approval.

TweetClaw does not replace WatchBot's dashboard or Hermes plugin tools. Treat it
as the OpenClaw-side collection and action layer, then bring summarized IDs,
URLs, counts, or alert notes back into WatchBot or the Hermes session.

## Setup

Install the official OpenClaw plugin from npm:

```bash
openclaw plugins install @xquik/tweetclaw
```

Store the Xquik API key in OpenClaw plugin config:

```bash
openclaw config set plugins.entries.tweetclaw.config.apiKey "$XQUIK_API_KEY"
```

Allow the plugin tools only when the current OpenClaw profile needs them:

```bash
openclaw config set tools.alsoAllow '["explore", "tweetclaw"]'
openclaw plugins inspect tweetclaw --runtime
```

## Credential Boundaries

- Keep WatchBot's `X_API_TOKEN` or `TWITTER_API_TOKEN` for the native `xurl`
  monitor.
- Keep `XQUIK_API_KEY` in OpenClaw's TweetClaw plugin config.
- Do not paste API keys, cookies, raw X credentials, or dashboard secrets into
  prompts, README examples, alert text, or saved WatchBot state.
- Connect or reauthenticate X accounts through the Xquik dashboard, not through
  WatchBot or a chat prompt.

## Example Flow

1. Run `hermes watchbot twitter` to see whether the timeline or keyword monitor
   has activity.
2. If the user asks for source details, use TweetClaw's free `explore` tool to
   find the right endpoint.
3. Call `tweetclaw` with a narrow read limit, such as tweet search or search
   tweet replies.
4. Return only the relevant tweet IDs, URLs, counts, and short summaries to the
   Hermes session.
5. Ask for explicit approval before any post, reply, DM, media, monitor,
   webhook, extraction, or giveaway draw action.
