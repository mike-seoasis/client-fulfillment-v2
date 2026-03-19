# UX Diagram Conventions

All diagrams use [Mermaid](https://mermaid.js.org/) syntax. Paste into [Mermaid Live Editor](https://mermaid.live) to render.

## Visual Language

### Node Shapes
| Shape | Meaning | Syntax |
|-------|---------|--------|
| Rectangle `[text]` | Screen / Page | `A[Dashboard]` |
| Rounded `(text)` | User Action | `A(Click Upload)` |
| Stadium `([text])` | System Process (AI, API) | `A([Claude generates])` |
| Diamond `{text}` | Decision Point | `A{Approved?}` |
| Circle `((text))` | Start / End | `A((Start))` |
| Hexagon `{{text}}` | Gate / Requirement | `A{{All keywords approved}}` |

### Node Styles (classDef)
| Class | Color | Meaning |
|-------|-------|---------|
| `screen` | `fill:#F5F0E8,stroke:#8B7D6B` | Screen/Page (sand) |
| `action` | `fill:#E8F5E9,stroke:#5B8C5A` | User Action (palm green) |
| `system` | `fill:#E0F2F1,stroke:#4A9B8E` | System/Backend Process (lagoon) |
| `decision` | `fill:#FFF3E0,stroke:#D4956A` | Decision Point (coral) |
| `gate` | `fill:#FCE4EC,stroke:#C97B84` | Blocking Gate (soft red) |
| `error` | `fill:#FFEBEE,stroke:#C62828` | Error State (red) |
| `start` | `fill:#C8E6C9,stroke:#388E3C` | Start node (green) |
| `complete` | `fill:#C8E6C9,stroke:#388E3C` | Complete/Success (green) |

### Edge Styles
| Style | Meaning | Syntax |
|-------|---------|--------|
| Solid arrow `-->` | Normal flow | `A --> B` |
| Labeled arrow `-->\|text\|` | Conditional flow | `A -->\|yes\| B` |
| Dotted arrow `-.->` | Async / background process | `A -.-> B` |
| Thick arrow `==>` | Primary / happy path | `A ==> B` |

### Subgraph Usage
- Each **step/phase** gets a subgraph with a clear title
- Subgraphs use `direction TB` (top-to-bottom) internally
- Main flow between subgraphs uses `direction LR` (left-to-right)

## File Naming
- `{tool}-overview.mmd` — High-level screen flow
- `{tool}-{step}.mmd` — Detailed interaction diagram per step
- Example: `onboarding-overview.mmd`, `onboarding-upload.mmd`

## Diagram Types Used
1. **Overview diagrams**: `flowchart LR` — Shows screens as nodes, navigation as edges
2. **Step detail diagrams**: `flowchart TD` — Shows every interaction within a single step
