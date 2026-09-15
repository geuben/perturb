# Sync and cache

How perturb gets issues from GitHub and keeps them in `.perturb/`. Using perturb only needs the
summary in [configuration.md](../configuration.md#cached-perturb-gitignored); this note is for working on
the code.

## Files

```
.perturb/
  github.json        # issues: number, title, state, labels, body head, blockedBy, blocking, parent, updatedAt
  graph.json         # structural edges after joining GitHub with repo artefacts
  meta.json          # last sync cursor (max updatedAt seen), synced_at, perturb version
```

## Sync

Every verb that needs GitHub syncs before it reads. `github.json` is refreshed incrementally via
GraphQL through the GitHub CLI (`gh`, or the command in `PERTURB_GH`), then `graph.json` is
rederived if HEAD, the cached issues or `perturb/config.yaml` changed. If GitHub is unreachable the
verb fails with `reason: "github_unreachable"` rather than answering from the cache. The cache
exists to make the sync incremental, not to serve stale answers.

GraphQL, one request per page of 50 issues, fields limited to what the model needs:

```graphql
query($owner:String!,$name:String!,$after:String){
  repository(owner:$owner,name:$name){
    issues(first:50,after:$after,states:[OPEN,CLOSED],orderBy:{field:UPDATED_AT,direction:DESC}){
      pageInfo{hasNextPage endCursor}
      nodes{
        number title state updatedAt
        labels(first:20){nodes{name}}
        parent{number}
        blockedBy(first:20){nodes{number state}}
        blocking(first:20){nodes{number state}}
        body
      }
    }
  }
}
```

`updatedAt` allows incremental sync: stop paging once a page's oldest `updatedAt` is before the
last sync. Closed issues stay in the cache because ready-ness depends on blocker state.

When a sync sees an issue's last open blocker close, it writes a pending `unblock` event into
`perturb/events/`. The first sync into an empty cache has no previous state and writes none.

## Test seam

`main(argv=None, *, transport=None, root=None, repo_root=None)`. `transport` must expose `.runner`
(same signature as `subprocess.run`) and `.graphql(query, variables) -> dict`; it defaults to
`GhTransport()`. `root` is the `.perturb/` directory and defaults to `<git-toplevel>/.perturb`.
`repo_root` is the git repository root, used to find plans and the ledger; it defaults to
`<git-toplevel>`.
