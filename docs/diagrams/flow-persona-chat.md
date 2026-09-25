# goat — business flow: persona-assisted coaching conversation

```mermaid
flowchart TD
    start([User asks a coaching question]) --> context[Load profile, active plan and selected personas]
    context --> stream[Stream response from coach agent]
    stream --> tool{Needs a product action?}
    tool -- No --> answer[Show coaching answer]
    tool -- Yes --> validate[Validate requested tool input]
    validate --> allowed{Action allowed by policy?}
    allowed -- No --> explain[Explain why no action was taken]
    allowed -- Yes --> execute[Read or write workout data]
    execute --> persist[Persist result and audit context]
    persist --> answer
    explain --> answer
    answer --> end([Conversation continues])
```
