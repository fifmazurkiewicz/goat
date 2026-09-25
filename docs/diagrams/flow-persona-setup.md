# goat — business flow: account and coaching-persona setup

```mermaid
flowchart TD
    start([User signs in with Google]) --> profile[Create or load training profile]
    profile --> goals[Collect goals, level, schedule and constraints]
    goals --> personas[Choose active coaching personas]
    personas --> limit{Within persona limit?}
    limit -- No --> adjust[Ask user to remove a selection]
    adjust --> personas
    limit -- Yes --> save[Save persona configuration]
    save --> end([Ready to plan and train])
```
