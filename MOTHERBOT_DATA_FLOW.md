# Motherbot Data Flow Architecture

## Complete System Architecture

```mermaid
graph TB
    subgraph "Motherbot"
        BOT[Bot Analysis Loop<br/>Every 3 mins]
        SQLITE[(SQLite<br/>Local DB)]
        FLASK[Flask Dashboard<br/>localhost:5000]
        LOGGER[TradingLogger]
        MOHA_LOGGER[MotherhavenLogger]

        BOT -->|Saves locally| LOGGER
        LOGGER -->|Writes| SQLITE
        LOGGER -->|Optional POST| MOHA_LOGGER
        SQLITE -->|Reads| FLASK
    end

    subgraph "Motherhaven Next.js (Production)"
        INGEST_API[Ingest API<br/>/api/llm-bot/ingest/*]
        FIREBASE[(Firebase<br/>Firestore)]
        FRONTEND[Next.js Frontend<br/>/llm-bot page]

        MOHA_LOGGER -->|HTTPS POST| INGEST_API
        INGEST_API -->|Writes| FIREBASE
        FIREBASE -->|Real-time listener| FRONTEND
    end

    subgraph "User Access"
        USER[User]
        USER -->|View local| FLASK
        USER -->|View production| FRONTEND
    end

    style BOT fill:#e1f5ff
    style SQLITE fill:#ffe1e1
    style FIREBASE fill:#fff4e1
    style FRONTEND fill:#e1ffe1
    style INGEST_API fill:#f0e1ff
```

---

## Detailed Data Flow by Operation

### 1. Bot Makes a Trading Decision

```mermaid
sequenceDiagram
    participant Bot as Python Bot
    participant Logger as TradingLogger
    participant SQLite as SQLite DB
    participant MohaLogger as MotherhavenLogger
    participant API as Next.js API
    participant Firebase as Firestore

    Bot->>Logger: log_decision(decision, raw_response)

    Note over Logger: ALWAYS writes locally first
    Logger->>SQLite: INSERT INTO decisions
    SQLite-->>Logger: ✓ Saved (id: 123)

    Note over Logger: THEN optionally syncs to cloud
    alt MOTHERHAVEN_ENABLED=true
        Logger->>MohaLogger: POST decision data
        MohaLogger->>API: POST /api/llm-bot/ingest/decision
        Note over API: Validates x-api-key header
        API->>Firebase: addDoc(llm-bot-decisions, {...})
        Firebase-->>API: ✓ Saved (id: abc123)
        API-->>MohaLogger: 200 OK
        MohaLogger-->>Logger: ✓ Synced
    else MOTHERHAVEN_ENABLED=false
        Note over Logger: Skip cloud sync<br/>Only local SQLite
    end

    Logger-->>Bot: ✓ Decision logged
```

---

### 2. Frontend Displays Data

```mermaid
sequenceDiagram
    participant User as User Browser
    participant Frontend as Next.js Frontend
    participant Firebase as Firestore

    User->>Frontend: Visit /llm-bot page

    Note over Frontend: ❌ OLD WAY (polling)<br/>fetch('/api/llm-bot/decisions')
    Note over Frontend: ✅ NEW WAY (real-time)

    Frontend->>Firebase: onSnapshot(collection('llm-bot-decisions'))
    Note over Firebase: Real-time listener established

    loop Every time data changes
        Firebase-->>Frontend: [new decision data]
        Frontend->>Frontend: Update React state
        Frontend-->>User: Display updated UI
    end

    Note over Frontend: No polling!<br/>No API calls for reads!<br/>Pure Firestore listeners
```

---

### 3. Complete Write Flow (Bot → Firebase)

```mermaid
graph LR
    subgraph "Bot Execution Cycle"
        A[Fetch Market Data] --> B[Analyze with Claude]
        B --> C[Get Decision]
        C --> D[Execute Trade]
    end

    subgraph "Logging to SQLite (Always)"
        D --> E[log_decision]
        E --> F[log_account_state]
        F --> G[log_position_entry]
        G --> H[update_decision_execution]
        H --> I[(SQLite)]
    end

    subgraph "Syncing to Firebase (Optional)"
        E --> J{MOTHERHAVEN<br/>ENABLED?}
        J -->|Yes| K[POST /ingest/decision]
        F --> L{MOTHERHAVEN<br/>ENABLED?}
        L -->|Yes| M[POST /ingest/account]
        G --> N{MOTHERHAVEN<br/>ENABLED?}
        N -->|Yes| O[POST /ingest/position]
        H --> P{MOTHERHAVEN<br/>ENABLED?}
        P -->|Yes| Q[POST /ingest/status]

        K --> R[(Firestore)]
        M --> R
        O --> R
        Q --> R
    end

    style I fill:#ffe1e1
    style R fill:#fff4e1
```

---

### 4. Read Flows (Two Interfaces)

```mermaid
graph TB
    subgraph "Local Flask Dashboard (Port 5000)"
        USER1[User] -->|Browse to localhost:5000| FLASK[Flask Web Server]
        FLASK -->|SELECT * FROM| SQLITE[(SQLite DB)]
        SQLITE -->|Returns rows| FLASK
        FLASK -->|Renders HTML| USER1
    end

    subgraph "Production Next.js Dashboard (motherhaven.app)"
        USER2[User] -->|Browse to /llm-bot| NEXTJS[Next.js Frontend]
        NEXTJS -->|onSnapshot| FIRESTORE[(Firestore)]
        FIRESTORE -->|Real-time updates| NEXTJS
        NEXTJS -->|Renders React| USER2
    end

    subgraph "Data Source"
        BOT[Python Bot] -->|Writes| SQLITE
        BOT -->|POST via API| FIRESTORE
    end

    style SQLITE fill:#ffe1e1
    style FIRESTORE fill:#fff4e1
```

---

## API Endpoint Purposes

### ❌ WRONG: Frontend Polling API for Reads

```typescript
// ❌ DON'T DO THIS
const { decisions, loading } = useBotDecisions(); // Polls /api/llm-bot/decisions

useEffect(() => {
  const interval = setInterval(() => {
    fetch('/api/llm-bot/decisions'); // ❌ Hitting API every 10s
  }, 10000);
}, []);
```

### ✅ CORRECT: Frontend Using Firestore Listeners

```typescript
// ✅ DO THIS
import { db } from "@/firebase";
import { collection, onSnapshot, query, orderBy, limit } from "firebase/firestore";

const [decisions, setDecisions] = useState([]);

useEffect(() => {
  const q = query(
    collection(db, "llm-bot-decisions"),
    orderBy("timestamp", "desc"),
    limit(50)
  );

  // Real-time listener - no polling!
  const unsubscribe = onSnapshot(q, (snapshot) => {
    const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    setDecisions(data);
  });

  return () => unsubscribe(); // Cleanup
}, []);
```

---

## API Endpoints Table

| Endpoint | Method | Purpose | Who Calls It | Returns |
|----------|--------|---------|--------------|---------|
| `/api/llm-bot/ingest/decision` | POST | Write decision to Firebase | **Bot only** | `{ success: true }` |
| `/api/llm-bot/ingest/account` | POST | Write account state to Firebase | **Bot only** | `{ success: true }` |
| `/api/llm-bot/ingest/position` | POST | Write position to Firebase | **Bot only** | `{ success: true }` |
| `/api/llm-bot/ingest/status` | POST | Write status to Firebase | **Bot only** | `{ success: true }` |
| `/api/llm-bot/decisions` | GET | ❌ **DEPRECATED** - Use Firestore | ~~Frontend~~ | Decision array |
| `/api/llm-bot/positions` | GET | ❌ **DEPRECATED** - Use Firestore | ~~Frontend~~ | Position array |
| `/api/llm-bot/account` | GET | ❌ **DEPRECATED** - Use Firestore | ~~Frontend~~ | Account object |
| `/api/llm-bot/status` | GET | ❌ **DEPRECATED** - Use Firestore | ~~Frontend~~ | Status object |

**Note:** The GET endpoints can be removed once frontend switches to Firestore listeners.

---

## Firebase Collections Structure

```
firestore
├── llm-bot-decisions/
│   ├── {docId}/
│   │   ├── timestamp: "2025-11-29T12:00:00Z"
│   │   ├── coin: "BTC/USDC:USDC"
│   │   ├── signal: "buy_to_enter"
│   │   ├── execution_status: "failed"
│   │   ├── execution_error: "Insufficient balance"
│   │   └── ...
│
├── llm-bot-positions/
│   ├── {docId}/
│   │   ├── position_id: "BTC_20251129_120000"
│   │   ├── coin: "BTC/USDC:USDC"
│   │   ├── status: "open"
│   │   └── ...
│
├── llm-bot-account/
│   ├── {docId}/
│   │   ├── timestamp: "2025-11-29T12:00:00Z"
│   │   ├── balance_usd: 29.06
│   │   ├── equity_usd: 29.06
│   │   └── ...
│
└── llm-bot-status/
    ├── {docId}/
        ├── timestamp: "2025-11-29T12:00:00Z"
        ├── status: "running"
        ├── message: "Executed hold for BTC/USDC:USDC"
        └── ...
```

---

## Data Consistency Model

```mermaid
graph TD
    A[Bot Makes Decision] --> B{Write to SQLite}
    B -->|Success| C[Local Data Available]
    B -->|Failure| D[Bot Crashes/Logs Error]

    C --> E{MOTHERHAVEN_ENABLED?}
    E -->|No| F[Done - SQLite Only]
    E -->|Yes| G{Write to Firebase via API}

    G -->|Success| H[Cloud Sync Complete]
    G -->|Failure| I[Warning Logged<br/>Bot Continues]

    I --> J[Data in SQLite Only]
    H --> K[Data in Both SQLite & Firebase]

    K --> L[Visible in Production Dashboard]
    J --> M[Visible in Local Flask Only]

    style F fill:#ffe1e1
    style K fill:#e1ffe1
    style J fill:#fff4e1
```

**Key Points:**
1. **SQLite is the source of truth** for the bot
2. **Firebase is optional sync** - bot continues if sync fails
3. **No bidirectional sync** - changes in Firebase don't flow back to SQLite
4. **Local Flask reads SQLite** (always accurate)
5. **Production Next.js reads Firebase** (may lag if sync fails)

---

## Summary

### ✅ Correct Architecture

**Bot (Python):**
- ✅ Writes to SQLite (always)
- ✅ POSTs to `/api/llm-bot/ingest/*` (when enabled)
- ✅ Flask reads from SQLite (local dashboard)

**API (Next.js):**
- ✅ Receives POSTs from bot
- ✅ Writes to Firestore
- ❌ ~~Should NOT serve reads to frontend~~

**Frontend (Next.js):**
- ✅ Uses Firestore listeners (real-time)
- ❌ ~~Should NOT poll API endpoints~~

### 🔧 What Needs to Change

1. **Replace all `useBotDecisions`, `useBotPositions`, etc. hooks** with Firestore listeners
2. **Remove GET endpoints** from `/api/llm-bot/*` (or deprecate)
3. **Update frontend components** to use `onSnapshot` instead of `fetch`

---

## Migration Checklist

- [x] Replace `useBotDecisions` with Firestore listener
- [x] Replace `useBotPositions` with Firestore listener
- [x] Replace `useBotAccount` with Firestore listener
- [x] Replace `useBotStatus` with Firestore listener
- [x] Replace `useBotErrors` with Firestore listener
- [x] Test real-time updates
- [ ] Remove deprecated API GET endpoints (optional cleanup)
- [x] Update documentation

✅ **Migration Complete!** All hooks now use Firebase real-time listeners instead of polling.

