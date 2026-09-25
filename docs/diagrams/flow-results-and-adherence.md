# goat — business flow: workout results and adherence tracking

```mermaid
flowchart TD
    start([User completes or skips a workout]) --> log[Record exercises, sets, reps and notes]
    log --> validate{Data valid?}
    validate -- No --> correct[Ask user to correct the entry]
    correct --> log
    validate -- Yes --> save[Persist workout result]
    save --> calculate[Update adherence and training-history metrics]
    calculate --> signal{Needs coaching follow-up?}
    signal -- Yes --> prompt[Surface suggested adjustment or coach prompt]
    signal -- No --> dashboard[Refresh progress view]
    prompt --> dashboard
    dashboard --> end([Updated training record])
```
